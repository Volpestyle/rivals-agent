"""Fresh-process identity check; prints only profile/workspace identifiers."""
import json,sys
from lifecycle import connect_verified
if __name__=="__main__":
    _,identity=connect_verified(json.loads(sys.argv[1]))
    print(json.dumps(identity))
