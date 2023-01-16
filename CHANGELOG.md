# Cleep-cli

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

