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

__all__ = ("Scheduler",)


from ..logger import getLogger
from .. import models
from . import DB, Jobs, Data
import threading
import time
import json


logger = getLogger(__name__.split(".", 1)[-1])


class Scheduler(threading.Thread):
    def __init__(self, job_handler: Jobs, db_handler: DB, data_handler: Data, delay: int):
        super().__init__(name="scheduler-handler", daemon=True)
        self.__job_handler = job_handler
        self.__db_handler = db_handler
        self.__data_handler = data_handler
        self.__delay = delay

    def run(self) -> None:
        while True:
            try:
                time.sleep(self.__delay)
                logger.debug("scheduling jobs ...")
                for weibull_id in self.__db_handler.list_keys(b"weibull-"):
                    try:
                        weibull = models.Weibull(json.loads(self.__db_handler.get(b"weibull-", weibull_id.encode())))
                        meta_data = self.__data_handler.get_metadata(weibull.service_id)
                        if meta_data.checksum != weibull.data_checksum:
                            self.__job_handler.create(weibull_id=weibull_id)
                    except Exception as ex:
                        logger.error("scheduling job for weibull '{}' failed - {}".format(weibull_id, ex))
            except Exception as ex:
                logger.error("scheduling jobs failed - {}".format(ex))
