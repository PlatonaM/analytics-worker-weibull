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

__all__ = ("Jobs",)


from ..logger import getLogger
from .. import weibull
from .. import models
from . import DB, Data
import threading
import queue
import typing
import uuid
import datetime
import base64
import gzip
import json
import time


logger = getLogger(__name__.split(".", 1)[-1])


class Worker(threading.Thread):
    def __init__(self, job: models.Job, db_handler: DB, data_handler: Data):
        super().__init__(name="jobs-worker-{}".format(job.id), daemon=True)
        self.__db_handler = db_handler
        self.__data_handler = data_handler
        self.__job = job
        self.done = False

    def run(self) -> None:
        try:
            logger.debug("starting job '{}' ...".format(self.__job.id))
            self.__job.status = models.JobStatus.running
            _weibull = models.Weibull(json.loads(self.__db_handler.get(b"weibull-", self.__job.weibull_id.encode())))
            file_path, time_field, _weibull.data_checksum = self.__data_handler.get(source_id=_weibull.service_id)
            logger.debug(
                "{}: calculating weibull distribution for '{}' in '{}' ...".format(
                    self.__job.id, _weibull.config["target_error_code"],
                    _weibull.config["target_col"]
                )
            )
            _weibull.result = weibull.generate_weibull(
                df=weibull.df_from_csv(
                    csv_path=file_path,
                    time_col=time_field,
                    sorted=True
                ),
                errorcode_column=_weibull.config["target_col"],
                errorcode=_weibull.config["target_error_code"]
            )
            _weibull.created = "{}Z".format(datetime.datetime.utcnow().isoformat())
            self.__db_handler.put(b"weibull-", _weibull.id.encode(), json.dumps(dict(_weibull)).encode())
            self.__job.status = models.JobStatus.finished
            logger.debug("{}: completed successfully".format(self.__job.id))
        except Exception as ex:
            self.__job.status = models.JobStatus.failed
            self.__job.reason = str(ex)
            logger.error("{}: failed - {}".format(self.__job.id, ex))
        self.__db_handler.put(b"jobs-", self.__job.id.encode(), json.dumps(dict(self.__job)).encode())
        self.done = True


class Jobs(threading.Thread):
    def __init__(self, db_handler: DB, data_handler: Data, check_delay: typing.Union[int, float], max_jobs: int):
        super().__init__(name="jobs-handler", daemon=True)
        self.__db_handler = db_handler
        self.__data_handler = data_handler
        self.__check_delay = check_delay
        self.__max_jobs = max_jobs
        self.__job_queue = queue.Queue()
        self.__job_pool: typing.Dict[str, models.Job] = dict()
        self.__worker_pool: typing.Dict[str, Worker] = dict()

    def create(self, weibull_id: str) -> str:
        for job in self.__job_pool.values():
            if job.weibull_id == weibull_id:
                logger.debug("job for weibull ID '{}' already exists".format(weibull_id))
                return job.id
        job = models.Job(
            id=uuid.uuid4().hex,
            weibull_id=weibull_id,
            created="{}Z".format(datetime.datetime.utcnow().isoformat())
        )
        self.__job_pool[job.id] = job
        logger.debug("created job for weibull ID '{}'".format(weibull_id))
        self.__job_queue.put_nowait(job.id)
        return job.id

    def get_job(self, job_id: str) -> models.Job:
        return self.__job_pool[job_id]

    def list_jobs(self) -> list:
        return list(self.__job_pool.keys())

    def run(self):
        while True:
            try:
                if len(self.__worker_pool) < self.__max_jobs:
                    try:
                        job_id = self.__job_queue.get(timeout=self.__check_delay)
                        worker = Worker(
                            job=self.__job_pool[job_id],
                            db_handler=self.__db_handler,
                            data_handler=self.__data_handler
                        )
                        self.__worker_pool[job_id] = worker
                        worker.start()
                    except queue.Empty:
                        pass
                else:
                    time.sleep(self.__check_delay)
                for job_id in list(self.__worker_pool.keys()):
                    if self.__worker_pool[job_id].done:
                        del self.__worker_pool[job_id]
                        del self.__job_pool[job_id]
                        # self.__db_handler.delete(b"jobs-", job_id.encode())
            except Exception as ex:
                logger.error("job handling failed - {}".format(ex))
