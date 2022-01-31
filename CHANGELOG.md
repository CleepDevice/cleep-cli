# Cleep-cli

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

