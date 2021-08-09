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

__all__ = ("conf",)


import simple_env_var


@simple_env_var.configuration
class Conf:

    @simple_env_var.section
    class Logger:
        level = "info"

    @simple_env_var.section
    class Storage:
        db_path = "/db"
        data_cache_path = "/data_cache"

    @simple_env_var.section
    class Data:
        api_url = "http://test"
        max_age = 1800

    @simple_env_var.section
    class Jobs:
        max_num = 5
        check = 5
        skd_delay = 600
        skd_enabled = True


conf = Conf(load=False)
