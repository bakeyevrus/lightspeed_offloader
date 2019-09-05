# Lightspeed offloader

The project stands for submitting exported eCommerce orders into [Lightspeed](https://www.lightspeed.com/) via REST API.
After the order is created in Lightspeed shop, an output CSV file with order status is created. 
Monitoring script is responsible for tracking status changes, and creating a new CSV file if the event has occurred.

The application consists of two modules.

## Prerequisites
- *Python 3.6* or higher
- *pip* package manager
- *crontab* tool for Linux

## Installation
This section covers application installation topic for **development purposes**. Installation instructions for **production**
environment is located in section *Deployment*.
1. In order to install application dependencies execute from the root directory:
    ```shell script
    pip install -r requirements.txt
    ``` 
2. If you are using the standard log config, make sure that `logs/` folder exists in the directory from which you are 
   starting the script.
3. The application requires SFTP password and Lightspeed API secret to be present in config file. For the sake of security,
    these strings should be encrypted using `password_encryption.py` utility. From the root directory execute:
    ```shell script
    python common/password_encryption.py -w <path_to_the_output_file>.enc
    ```
   You will be asked for the master password, which should be added to the application config. 


## Starting

Execute in the terminal from the root directory:
```shell script
python -m <module_name> -c config/<path_to_app_config>.yaml -l config/<path_to_log_config>.yaml
```

The application consts of two modules:
 - `lightspeed_offloader`
 - `status_checker`
 
Each of the modules uses the same application and log configs. See below for a config description. 

## Application config
|           Property           |                                                                 Description                                                                 |              Example             |
|:----------------------------:|:-------------------------------------------------------------------------------------------------------------------------------------------:|:--------------------------------:|
| sftp-host                    | SFTP server hostname.                                                                                                                       | "mysftp.example.com"             |
| sftp-port                    | SFTP server port. 22 is mostly used as default.                                                                                             | 22                               |
| sftp-user                    | SFTP user.                                                                                                                                  | "root"                           |
| sftp-pass-path               | Path to the encrypted SFTP password.                                                                                                        | "./config/sftp-pass.enc"         |
| sftp-input-folder            | A folder on the SFTP server, which contains exported eCommerce orders in CSV format.                                                        | "out"                            |
| sftp-output-folder           | A folder on the SFTP server, which contains order statuses in CSV format.                                                                   | "in"                             |
| sftp-archive-folder          | A folder on the SFTP server, which processed, 'confirmed', or 'shipped' orders moved to.                                                    | "archiv"                         |
| lightspeed-api-url           | Base URL for the Lightspeed shop.                                                                                                           | "https://api.webshopapp.com/nl"  |
| lightspeed-api-key           | Lightspeed shop API key. See [docs](https://developers.lightspeedhq.com/ecom/introduction/authentication/).                                 | "somerandomekey"                 |
| lightspeed-api-secret-path   | Path to the encrypted Lightspeed API secret token.                                                                                          | "./config/lightspeed-secret.enc" |
| lightspeed-shipment-id       | An id of the shipment method to use. See [docs](https://developers.lightspeedhq.com/ecom/endpoints/shippingmethod/).                        | "12345"                          |
| lightspeed-shipment-value-id | A value id of the shipment method to use. See [docs](https://developers.lightspeedhq.com/ecom/endpoints/shippingmethodvalue/).              | "67890"                          |
| master-password              | Password which has been used to encrypt both the SFTP password and Lightspeed API secret.                                                   | "VeryStrongAndSecretPassword"    |

Note the quotes in the *Example* column.


## Deployment
Navigate to the `scripts/` folder and execute:
```shell script
./deploy.sh <absolute_path_to_the_root_folder_of_this_repository>
```
`deploy.sh` script performs the following steps:
1. Checks if *Python* and *pip* are installed.
2. Installs application dependencies.
3. Creates `logs/` folder.
4. Checks if *crontab* installed.
5. Creates *crontab* jobs.

**IMPORTANT**, you have to set up `config.yaml` (see section *Application config*) and encrypt passwords (see section
*Installation*) on your own. 

## Docker for development
To develop inside the Docker container **from the root directory** execute the following (for Windows only):
```shell script
docker pull python:3.7
docker run -d -it --name lightspeed-offloader -v "%cd%":/src python:3.7 
docker exec -it lightspeed-offloader /bin/bash
```
Inside the container `/src` folder will be created with the application source code.
