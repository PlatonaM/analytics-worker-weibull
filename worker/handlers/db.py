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

__all__ = ("DB",)


from ..logger import getLogger
import plyvel
import threading

logger = getLogger(__name__.split(".", 1)[-1])


class DB:
    def __init__(self, st_path):
        self.__kvs = plyvel.DB(st_path, create_if_missing=True)
        self.__lock = threading.Lock()

    def put(self, db: bytes, key: bytes, value: bytes):
        with self.__lock:
            partition = self.__kvs.prefixed_db(db)
            partition.put(key, value)

    def get(self, db: bytes, key: bytes) -> bytes:
        with self.__lock:
            partition = self.__kvs.prefixed_db(db)
            value = partition.get(key)
            if not value:
                raise KeyError(key)
            return value

    def delete(self, db: bytes, key: bytes):
        with self.__lock:
            partition = self.__kvs.prefixed_db(db)
            partition.delete(key)

    def list_keys(self, db: bytes) -> list:
        with self.__lock:
            partition = self.__kvs.prefixed_db(db)
            with partition.iterator() as it:
                return [key.decode() for key, _ in it]

    def close(self):
        with self.__lock:
            self.__kvs.close()