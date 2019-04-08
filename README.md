# Cleep-cli

This utility helps developers to build Cleep applications providing some useful commands:
* `coreget` to clone or pull official Cleep repository.
* `coresync` to synchronize sources from repository to execution folders.
* `modcreate` to create module (aka application) skeleton.
* `modsync` to synchronize sources from module folder to execution folders.
* `watch` to watch for repository filesystem changes and automatically update files on execution folders. It also restart backend or/and frontend according to changes.

## Installation
Cleep-cli is automatically installed and managed by Cleep developer application.

If you want to install it manually, execute following command:
> pip install cleepcli

## Compatibility
This cli can run on platform supporting python but `watch` command is only available on Raspbian distribution.

## Help
Execute this command to get help on this cli:
> cleep-cli --help

## Watch usage
Launch `watch` cli command to monitor changes on "/root/cleep" directory after cloning official repository.

Then open your favorite editor on your development computer, configure a remote sync plugin to push local changes on your raspberry pi then cleep-cli will synchronize sources on Cleep execution environment and restart application automatically.

### Visual studio code
Install Visual studio code [ftp-sync](https://marketplace.visualstudio.com/items?itemName=lukasz-wronski.ftp-sync) plugin and configure it to access your raspberry pi.

## How it works
This cli executes git commands to clone or update repository.

It uses rsync commands to synchronize files.

The [watchdog](https://pypi.org/project/watchdog/) python library is used to detect changes on filesystem. According to changed files, it detects if change occurs on frontend or backend files and send commands to running Cleep software.

