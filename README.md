# Cleep-cli

This utility helps developers to build Cleep applications providing some useful commands:
* Core commands:
    * `coreget` to clone or pull official Cleep repository.
    * `coredocs` to generate core documentation in HTML format.
    * `coresync` to synchronize sources from repository to execution folders.
    * `coretests` to perform core tests suite.
    * `coretestscov` to display last core tests code coverage report.
    * `cpuprof` to run CPU profiler on application execution instance.
    * `memprof` to run memory profiler on application execution instance.
    * `reset` clear existing installed Cleep files and install it again.
* Module commands:
    * `modcreate` to create module (aka application) skeleton.
    * `moddelete` to delete installed files of a module.
    * `moddocs` to generate module documentation.
    * `modsync` to synchronize sources from module folder to execution folders.
    * `modtests` to execute module tests.
    * `modtestscov` to display last module tests code coverage report.
    * `modbuild` to create application package (.zip)
    * `modcheckback` to check app backend (python files structure and content)
    * `modcheckfront` to check app frontend (js files and desc.json)
    * `modchecktests` to check app tests files
    * `modcheckscripts` to check app scripts files
    * `modcheckcode` to check backend code quality (run pylint)
* Watch commands:
    * `watch` to watch for repository filesystem changes and automatically update files on execution folders. It also restart backend or/and frontend according to changes.
* Misc commands:
    * `version` to get cleep-cli version

## Installation
Cleep-cli is automatically installed and managed by [Cleep developer](https://github.com/tangb/cleepmod-developer) application.

If you want to install it manually, execute following command:
> pip install cleepcli

## Compatibility
This cli is written in Python and is supposed to be used only on Raspbian platform for Cleep application development because it has harcoded paths.

## Help
Execute this command to get help on this cli:
> cleep-cli --help

## Watch usage
Launch `watch` cli command to monitor changes on "/root/cleep" directory after getting official Cleep repository using `coreget` command.

Then open your favorite editor on your development computer, configure a remote sync plugin to push local changes on your raspberry pi then cleep-cli will synchronize sources on Cleep execution environment and restart application automatically.

### Paths
The cli clone repository on `/root/cleep` folder. Modules are in `/root/cleep/modules` folder.
So if you develop on Cleep core, your editor must sync to `/root/cleep` remote directory while if you're developping only on a module your editor must sync to `/root/cleep/modules/<your module name>` remote directory.

### Visual studio code
Install Visual studio code [sftp](https://marketplace.visualstudio.com/items?itemName=liximomo.sftp) plugin and configure it to access your raspberry pi:
* Open VSCode command palette pressing CTRL-SHIFT-P
* Type "sftp: config"
* Fill opened file with:

```
{
    "name": "cleep",
    "host": "<raspberry pi ip address>",
    "protocol": "sftp",
    "port": 22,
    "username": "root",
    "remotePath": "/root/cleep/modules/<your module>/" or "/root/cleep/",
    "uploadOnSave": false,
    "syncOption": {
        "delete": true,
        "skipCreate": false,
        "ignoreExisting": false,
        "update": false
    },
    "watcher": {
        "files": "**/*.{sh,py,js,css,html,json}",
        "autoUpload": true,
        "autoDelete": true
    }
}
```

### Local developments
If you want to develop directly on the raspberry using vim or nano, simply develop on `/root/cleep/` directory. Cleep-cli watcher will synchronize all your modifications.

## How it works
This cli executes git commands to clone or update repository.

It uses rsync commands to synchronize files.

It uses pylint to check code quality (it returns a score)

The [watchdog](https://pypi.org/project/watchdog/) python library is used to detect changes on filesystem. According to changed files, it detects if change occurs on frontend or backend files and send commands to restart Cleep application.

