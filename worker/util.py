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

__all__ = ("Decompress", )


import zlib
import typing
import hashlib


def get_hash(service_id: str, config: dict) -> str:
    conf_ls = ["{}{}".format(key, val) for key, val in config.items()]
    conf_ls.sort()
    srv_conf_str = service_id + "".join(conf_ls)
    return hashlib.sha256(srv_conf_str.encode()).hexdigest()


class Decompress:
    def __init__(self, io_obj: typing.BinaryIO, wbits: int = zlib.MAX_WBITS | 16):
        self.__io_obj = io_obj
        self.__decomp_obj = zlib.decompressobj(wbits=wbits)

    def write(self, b: bytes):
        return self.__io_obj.write(self.__decomp_obj.decompress(b))

    def flush(self) -> bytes:
        self.__io_obj.write(self.__decomp_obj.flush())
        return self.__decomp_obj.flush()

    def close(self):
        self.__io_obj.write(self.__decomp_obj.flush())
        return self.__io_obj.close()

    def __getattr__(self, attr):
        return getattr(self.__io_obj, attr)
