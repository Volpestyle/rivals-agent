set -uo pipefail
cd /Users/james/dev/idm-data/expanded-refit-d4f05e0/runtime-full03-05a61b4/code || exit 97
export PYTHONPATH="$PWD"
export MODAL_PROFILE=rivals
export PYTHONDONTWRITEBYTECODE=1
/Users/james/.local/share/uv/tools/modal/bin/python -m cloud.modal_guard run \
 /Users/james/dev/idm-data/expanded-refit-d4f05e0/idm-expanded-20260928-full-03/spec.json \
 a30d4f55a395a014b816734076c211e37137b8ac98e162dd5ed49d61df5e874f \
 e7fb306cfb7fa3f7e9047b78ef85a4824071c5a29eb17d6c85957f8d03531823
code=$?
print -r -- "$code" > /Users/james/dev/idm-data/expanded-refit-d4f05e0/idm-expanded-20260928-full-03/run.exit
exit "$code"
