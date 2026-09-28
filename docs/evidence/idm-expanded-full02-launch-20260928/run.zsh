set -uo pipefail
cd /Users/james/dev/idm-data/expanded-refit-d4f05e0/runtime-local-timing-adda577/code || exit 97
export PYTHONPATH="$PWD"
export MODAL_PROFILE=rivals
export PYTHONDONTWRITEBYTECODE=1
/Users/james/.local/share/uv/tools/modal/bin/python -m cloud.modal_guard run \
 /Users/james/dev/idm-data/expanded-refit-d4f05e0/idm-expanded-20260928-full-02/spec.json \
 4d566c85e5447282e2d77757b10d27f5ce4f14ccb9b45b23195e09211fcf16e3 \
 4a4d57d5ec2b97566b5bc59f212c8f4b9357198fe0eb7270874902079bdd8af6
code=$?
print -r -- "$code" > /Users/james/dev/idm-data/expanded-refit-d4f05e0/idm-expanded-20260928-full-02/run.exit
exit "$code"
