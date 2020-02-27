# dPlauy

A simple tool to deploy an application to a set of servers. Not meant for large-scale deploys.

## Requirements
- [Python3](https://docs.python.org/3/using/index.html)
- [toml](https://pypi.org/project/toml/)
- [paramiko](https://pypi.org/project/paramiko/)

## Assumptions
- The server is running Linux with systemd.

## Usage
- Create a file `dPlauy.toml` in the project that needs to be deployed. This file includes information about what is to deployed and how it is to be deployed. See the [sample](sample.toml) for more information.

```shell
python3 deploy.py ../path-to-project env=dev,preprod
```
