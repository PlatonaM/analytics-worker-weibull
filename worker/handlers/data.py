"""
   Copyright 2021 InfAI (CC SES)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

__all__ = ("Data", )


from ..logger import getLogger
from .. import util, models
import requests
import os
import time
import typing
import threading
import urllib.parse
import uuid
import hashlib


logger = getLogger(__name__.split(".", 1)[-1])


class CacheItem:
    def __init__(self):
        self.file = None
        self.checksum = None
        self.created = None
        self.time_field = None
        self.lock = threading.Lock()


class Data(threading.Thread):
    __chunk_size = 65536

    def __init__(self, st_path: str, data_api_url: str, max_age: int):
        super().__init__(name="data-handler", daemon=True)
        self.__st_path = st_path
        self.__data_api_url = data_api_url
        self.__max_age = max_age
        self.__cache: typing.Dict[str, CacheItem] = dict()
        self.__lock = threading.Lock()

    def get_metadata(self, source_id: str) -> models.MetaData:
        resp = requests.get(url="{}/{}".format(self.__data_api_url, urllib.parse.quote(source_id)))
        if not resp.ok:
            raise RuntimeError(resp.status_code)
        metadata = models.MetaData(resp.json())
        if not metadata.checksum:
            raise RuntimeError("no data available for '{}'".format(source_id))
        return metadata

    def __get_data(self, source_id: str, compressed: bool):
        with requests.get(url="{}/{}/file".format(self.__data_api_url, urllib.parse.quote(source_id)), stream=True) as resp:
            if not resp.ok:
                raise RuntimeError(resp.status_code)
            file_name = uuid.uuid4().hex
            checksum = hashlib.sha256()
            with open(os.path.join(self.__st_path, file_name), "wb") as file:
                if compressed:
                    file = util.Decompress(file)
                buffer = resp.raw.read(self.__chunk_size)
                checksum.update(buffer)
                while buffer:
                    file.write(buffer)
                    buffer = resp.raw.read(self.__chunk_size)
                    checksum.update(buffer)
        return file_name, checksum.hexdigest()

    def __get_new(self, source_id: str):
        metadata = self.get_metadata(source_id)
        file_name, checksum = self.__get_data(source_id, metadata.compressed)
        count = 0
        while metadata.checksum != checksum:
            if count > 3:
                raise RuntimeError("checksum mismatch for '{}' - data might have changed")
            logger.warning("checksum mismatch for '{}' - refreshing metadata".format(source_id))
            metadata = self.get_metadata(source_id)
            count = count + 1
        return file_name, metadata.checksum, metadata.time_field

    def __refresh_cache_item(self, source_id: str, cache_item: CacheItem):
        cache_item.file, cache_item.checksum, cache_item.time_field = self.__get_new(source_id=source_id)

    def get(self, source_id: str) -> typing.Tuple[str, str, str]:
        with self.__lock:
            if source_id not in self.__cache:
                self.__cache[source_id] = CacheItem()
        cache_item = self.__cache[source_id]
        with cache_item.lock:
            if not cache_item.file:
                self.__refresh_cache_item(source_id, cache_item)
                cache_item.created = time.time()
            elif time.time() - cache_item.created > self.__max_age:
                metadata = self.get_metadata(source_id)
                if metadata.checksum != cache_item.checksum:
                    old_file = cache_item.file
                    self.__refresh_cache_item(source_id, cache_item)
                    try:
                        os.remove(os.path.join(self.__st_path, old_file))
                    except Exception as ex:
                        logger.warning("could not remove stale data - {}".format(ex))
                cache_item.created = time.time()
            return os.path.join(self.__st_path, cache_item.file), cache_item.time_field, cache_item.checksum

    def run(self) -> None:
        stale_items = list()
        while True:
            time.sleep(self.__max_age / 2)
            with self.__lock:
                for key, item in self.__cache.items():
                    if time.time() - item.created > self.__max_age and not item.lock.locked():
                        stale_items.append(key)
                for key in stale_items:
                    try:
                        os.remove(os.path.join(self.__st_path, self.__cache[key].file))
                    except Exception as ex:
                        logger.warning("could not remove stale data - {}".format(ex))
                    del self.__cache[key]
            stale_items.clear()

    def purge_cache(self):
        for file in os.listdir(self.__st_path):
            try:
                os.remove(os.path.join(self.__st_path, file))
            except Exception:
                pass
