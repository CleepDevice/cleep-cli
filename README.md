# Cleep-cli

This utility helps developers to build Cleep applications providing some useful commands:
* `coreget` to clone or pull official Cleep repository.
* `coresync` to synchronize sources from repository to execution folders.
* `modcreate` to create module (aka application) skeleton.
* `modsync` to synchronize sources from module folder to execution folders.
* `watch` to watch for repository filesystem changes and automatically update files on execution folders. It also restart backend or/and frontend according to changes.

## Installation
Cleep-cli is automatically installed and managed by [Cleep developer](https://github.com/tangb/cleepmod-developer) application.

If you want to install it manually, execute following command:
> pip install cleepcli

## Compatibility
This cli is developed in Python and is supposed to be used on Raspbian platform for Cleep application development because it has harcoded path.

## Help
Execute this command to get help on this cli:
> cleep-cli --help

## Watch usage
Launch `watch` cli command to monitor changes on "/root/cleep" directory after cloning official repository.

Then open your favorite editor on your development computer, configure a remote sync plugin to push local changes on your raspberry pi then cleep-cli will synchronize sources on Cleep execution environment and restart application automatically.

### Visual studio code
Install Visual studio code [sftp](https://marketplace.visualstudio.com/items?itemName=liximomo.sftp) plugin and configure it to access your raspberry pi:
* Open VSCode command palette pressing CTRL-SHIFT-P
* Type "sftp: config"
* Fill opened file with:

```
{
    "name": "Cleep",
    "host": "raspberry pi ip address",
    "protocol": "sftp",
    "port": 22,
    "username": "root",
    "remotePath": "/root/cleep",
    "uploadOnSave": true
}
```

## How it works
This cli executes git commands to clone or update repository.

It uses rsync commands to synchronize files.

The [watchdog](https://pypi.org/project/watchdog/) python library is used to detect changes on filesystem. According to changed files, it detects if change occurs on frontend or backend files and send commands to restart Cleep application.

