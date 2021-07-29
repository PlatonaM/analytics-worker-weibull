## analytics-worker-weibull

Automated calculation of shape and scale parameters for weibull distributions for given error codes.

Shape and scale parameters and their corresponding error codes are stored as _weibull resources_.
In order for calculations to be performed, a weibull resource must be created via a _weibull request_.
A weibull request contains an error code, and the column in which the error code can occur.
Calculations are performed by jobs. A job is started automatically when new data is available.
Alternatively, jobs can also be triggered manually with a _job request_.

### Configuration

`CONF_LOGGER_LEVEL`: Set logging level to `info`, `warning`, `error`, `critical` or `debug`.

`CONF_STORAGE_DB_PATH`: Set database path.

`CONF_STORAGE_DATA_CACHE_PATH`: Set path for temporary files.

`CONF_DATA_API_URL`: Url of data service. **(required)**

`CONF_DATA_MAX_AGE`: Control internal cache.

`CONF_JOBS_MAX_NUM`: Set maximum number of parallel calculations.

`CONF_JOBS_CHECK`: Control how often the worker checks if new jobs are available.

`CONF_JOBS_SKD_DELAY`: Set the time between job scheduler runs.

### Data Structures

#### Job resource

    {
        "id": <string>,
        "created": <string>,
        "status": "<string>",
        "weibull_id": <string>,
        "reason": <string>
    }

#### Weibull resource

    {
        "id": <string>,
        "created": <string>,
        "config": {
            "target_col": <string>,
            "target_error_code": <number>
        },
        "result": {
            "shape_parameter": <number>,
            "scale_parameter": <number>
        },
        "service_id": <string>,
        "data_checksum": <string>
    }

#### Weibull request

    {
        "service_id": <string>,
        "config": {
            "target_col": <string>,
            "target_error_code": <number>
        }
    }

#### Job request

    {
        "weibull_id": <string>
    }

### API

#### /weibull

**GET**

_List IDs of all weibull resources._

    # Example    
    
    curl http://<host>/weibull
    [
        "16c320b42ef75103c24f02ce4dd4088e91bebde3d2d45b2732c2d16471f4ffdd",
        "cf7bf52cd74dd6071fe6d69717bbfa7c0ceb3e611bb8320be63293e605f97d44"
    ]

**POST**

_Send a weibull request to create a new weibull resource._

    # Example

    cat new_weibull_request.json
    {
        "service_id": "urn:infai:ses:service:c2872437-3e53-49c6-a5be-bf264d52430d",
        "config": {
            "target_col": "module_2_errorcode",
            "target_error_code": 1202
        }
    }

    curl \
    -d @new_weibull_request.json \
    -H 'Content-Type: application/json' \
    -X POST http://<host>/weibull

    # Response status 201 if created and 200 if resource alread exists
    # ID of weibull resource as response body (text/plain)

#### /weibull/{weibull_id}

**GET**

_Retrieve a weibull resource._

    # Example    
    
    curl http://<host>/weibull/cf7bf52cd74dd6071fe6d69717bbfa7c0ceb3e611bb8320be63293e605f97d44
    {
        "id": "cf7bf52cd74dd6071fe6d69717bbfa7c0ceb3e611bb8320be63293e605f97d44",
        "created": "2021-06-01T07:45:51.700434Z",
        "config": {
            "target_col": "module_2_errorcode",
            "target_error_code": 1202
        },
        "result": {
            "shape_parameter": 0.3720067479184128,
            "scale_parameter": 3347.3017326022227
        },
        "service_id": "urn:infai:ses:service:c2872437-3e53-49c6-a5be-bf264d52430d",
        "data_checksum": "82db633dc6936e4104f1c0fe9d927b3ae8f0f0e584a296a17ae5ce1bd82f5b84"
    }

#### /jobs

**GET**

_List IDs of all jobs._

    # Example    
    
    curl http://<host>/jobs
    {
        "current": [],
        "history": [
            "1c641b16c7b84a958cc7058c12a068ea",
            "314d123f779746129b6633d1d5dcfc74",
            "46b17692589049d7bcdc00f02218f93b",
            "48c455cfc2874350925bdf66919332bb",
            "59c6ed2788a046eb835174062f063b9a"
        ]
    }

**POST**

_Send a job request to start a job._

    # Example

    cat new_job_request.json
    {
        "weibull_id": "cf7bf52cd74dd6071fe6d69717bbfa7c0ceb3e611bb8320be63293e605f97d44"
    }
    
    curl \
    -d @new_job_request.json \
    -H 'Content-Type: application/json' \
    -X POST http://<host>/jobs

#### /jobs/{job_id}

**GET**

Retrieve job details.

    # Example
    
    curl http://<host>/jobs/ad1f2d3637574248b1a39d595833fa4b
    {
        "id": "ad1f2d3637574248b1a39d595833fa4b",
        "created": "2021-06-01T07:45:49.362369Z",
        "status": "finished",
        "weibull_id": "cf7bf52cd74dd6071fe6d69717bbfa7c0ceb3e611bb8320be63293e605f97d44",
        "reason": null
    }
