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

from worker.logger import initLogger
from worker.configuration import conf
from worker import handlers
from worker import api
import falcon


initLogger(conf.Logger.level)

db_handler = handlers.DB(st_path=conf.Storage.db_path)
data_handler = handlers.Data(
    st_path=conf.Storage.data_cache_path,
    data_api_url=conf.Data.api_url,
    max_age=conf.Data.max_age
)
jobs_handler = handlers.Jobs(
    db_handler=db_handler,
    data_handler=data_handler,
    check_delay=conf.Jobs.check,
    max_jobs=conf.Jobs.max_num
)
skd_handler = handlers.Scheduler(
    job_handler=jobs_handler,
    db_handler=db_handler,
    data_handler=data_handler,
    delay=conf.Jobs.skd_delay
)

app = falcon.API()

app.req_options.strip_url_path_trailing_slash = True

routes = (
    ("/weibull", api.WeibullCollection(db_handler=db_handler, jobs_handler=jobs_handler)),
    ("/weibull/{weibull_id}", api.WeibullResource(db_handler=db_handler)),
    ("/jobs", api.Jobs(db_handler=db_handler, jobs_handler=jobs_handler)),
    ("/jobs/{job_id}", api.Job(db_handler=db_handler, jobs_handler=jobs_handler))
)

for route in routes:
    app.add_route(*route)

data_handler.purge_cache()
jobs_handler.start()
data_handler.start()
if conf.Jobs.skd_enabled:
    skd_handler.start()
