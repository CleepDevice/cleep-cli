# Cleep-cli

# [1.43.4] - 2025-04-25
## Fixed
- Increase timeout of CI RPC commands to reduce failure when network is slow
- Fix issue during app doc generation

# [1.43.3] - 2025-02-10
## Fixed
- Fix modcheckdoc response output (json and text)

# [1.43.2] - 2025-02-07
## Fixed
- Return error when modcheckdoc failed

# [1.43.1] - 2025-02-03
## Fixed
- Pattern to detect correct usage of img in app html (cl-app-img or cl-img-src)

# [1.43.0] - 2024-11-12
## Added
- Add command to check Cleep version before building deb package

# [1.42.0] - 2024-11-12
## Added
- Update debian/control files according to packages.list before build Cleep deb package

## Fixed
- Return {} instead of None if documentation cmd return nothing

# [1.41.0] - 2024-10-22
## Added
- Add new option to pass already generated app documentation to cimoddocpublish

# [1.40.1] - 2024-10-15
## Fixed
- Add more log to debug app doc generation failure

# [1.40.0] - 2024-10-15
## Added
- Add way to run specific app tests based on pattern

# [1.39.2] - 2024-10-02
## Fixed
- Fix semver check for version string starting with v

# [1.39.1] - 2024-10-02
## Fixed
- Change way to get Cleep url to retrieve app documentation

## Added
- New ghowner arg in cimoddocpublish cmd to set repo owner

# [1.39.0] - 2024-09-23
## Added
- Add pattern parameter to coretests to run only matches

# [1.38.2] - 2024-04-04
## Fixed
- Run mandatory apps install scripts during cigetmods

# [1.38.1] - 2024-03-29
## Fixed
- Some info log breaks json output

# [1.38.0] - 2024-03-26
## Added
- Add tag option to corepublish

# [1.37.4] - 2024-03-20
## Fixed
- Change cleep api docs repo

# [1.37.3] - 2024-03-18
## Fixed
- Bump Sphinx dependency

# [1.37.2] - 2024-03-18
## Added
- Add way to generate coverage report to xml (only format supported by codacy)

## Fixed
- Typo: rename xxx_test to xxx_tests

# [1.37.1] - 2024-03-18
## Fixed
- Fixed issue with coretests cmd

# [1.37.0] - 2024-03-18
## Added
- Add prerelease flag to corepublish command

#" Fixed
- Issue when requesting core coverage with coretestscov cmd

# [1.36.0] - 2024-03-17
## Added
- Add way to pull specific branch for cigetmods command

# [1.35.1] - 2024-03-14
## Fixed
- Fix issue with get_module_name (occured after Click upgrade)
- Fix watch command filtering to not reload Cleep after useless changes (test, doc...)
- Fix some dependencies update (Click, watchdog)

# [1.35.0] - 2024-03-08
## Updated
- Add run-scripts to modssync

# [1.34.2] - 2024-03-07
## Fixed
- Create missing /etc/cleep dir
- Change modules destination dir (now /opt/cleep/modules)

# [1.34.1] - 2024-03-07
## Fixed
- Create missing Cleep install directories

# [1.34.0] - 2024-03-07
## Added
- Add new modssync command to sync all mandatory modules at once

## Fixed
- Create modules directory in cleep installation folder to allow CI to start from scratch

# [1.33.4] - 2024-03-07
## Fixed
- Change way to detect Cleep installation path

# [1.33.3] - 2024-02-23
## Updated
- Add way to pass github access token via command line for cimoddocpublish cmd

# [1.33.2] - 2024-01-17
## Fixed
- Fix issue parsing to json console stdout when checking app documentation

# [1.33.1] - 2024-01-16
## Fixed
- Restrict process name search in Tools.is_cleep_running function

# [1.33.0] - 2024-01-15
## Updated
- Find cleep rpc url from cleep logs

# [1.32.5] - 2023-12-29
## Fixed
- Handle console returncode instead of error flag

# [1.32.4] - 2023-12-29
## Fixed
- Sync cli dependencies with cleep ones

# [1.32.3] - 2023-12-29
## Fixed
- Add missing semver dependency

# [1.32.2] - 2023-11-09
## Fixed
- Fix core sync with modules dir symlink (always removed before)

# [1.32.1] - 2023-11-08
## Fixed
- Fix error logged when app doc file doesn't exists (it breaks cmd output)

# [1.32.0] - 2023-06-05
## Added
- Add modcheckbreakingchanges cmd to get app breaking changes

# [1.31.0] - 2023-04-25
## Added
- Add moddoc command to generate module documentation
- Add modcheckdoc command to check module documentation

## Changed
- Rename moddocs to modapidoc
- Rename moddocspath to modapidocpath

# [1.30.1] - 2023-04-25
## Fixed
- Remove useless git_password file

# [1.30.0] - 2023-03-29
## Added
- Handle auth on Cleep

# [1.29.4] - 2023-03-04
## Fixed
- Fix docs publishing when there is no changes

# [1.29.3] - 2023-03-03
## Changed
- Publish docs to cleep-docs repo

# [1.29.2] - 2023-03-03
## Changed
- Generate core docs from template

# [1.29.1] - 2023-02-20
## Added
- Add cigetmods sync option

# [1.29.0] - 2023-02-20
## Added
- Add cigetmods command

# [1.28.4] - 2023-02-04
## Fixed
- Fix core package publish

# [1.28.3] - 2023-01-30
## Fixed
- Fix core docs publication

# [1.28.2] - 2023-01-26
## Fixed
- Core docs generation

# [1.28.1] - 2023-01-25
## Fixed
- Add -o options to unzip command during coredocs publication
- Fix coredocs script error (command rf not found)

# [1.28.0] - 2023-01-25
## Changed
- Change paths to fit to CleepDevice github organization

# [1.27.0] - 2023-01-16
## Changed
- Improve core tests command adding new option to display tests output

## Added
- Introduce CI

# [1.26.13] - 2023-01-15
## Fixed
- Fix issue in package module (typo)

# [1.26.12] - 2023-01-15
## Fixed
- Fix issue in bin

# [1.26.11] - 2023-01-14
## Changed
- Configure logging as soon as possible

# [1.26.9] - 2023-01-14
## Changed
- Add way to configure REPO_DIR from env var

# [1.26.8] - 2023-01-14
## Fixed
- Handle last Cleep module imports

# [1.26.7] - 2023-01-14
## Fixed
- Remove code that depends of Cleep module

# [1.26.6] - 2023-01-14
## Fixed
- Typo core_tests
- Add missing passlib dependency

# [1.26.4] - 2022-02-01
## Fixed
- Fix issue with custom app name

# [1.26.3] - 2022-01-31
## Fixed
- Fix issue in command cimodinstall

# [1.26.2] - 2022-01-31
## Added
- Copy sources files during CI module install
- Improve package installation (more checkings, use health route)
- Update "update" application before app installation if necessary

# [1.26.1] - 2022-01-30
## Fixed
- Better compatibility handling during install from CI

# [1.26.0] - 2022-01-24
## Changed
- Replace urllib3 by requests to remove incompatibility warnings with Cleep

# [1.25.0] - 2022-01-24
## Added
- Change developement directory from /root/cleep to /root/cleep-dev to avoid ambiguity with installed package

# [1.24.1] - 2022-01-18
## Fixed
- Remove warning when multiple tests files

# [1.24.0] - 2022-01-18
## Added
- Handle multiple unittest files instead of single one
- Use app CATEGORIES from core common

