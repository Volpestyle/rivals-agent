"""Run the unchanged pinned A3 judge only with its approved Python interpreter."""
import hashlib,pathlib,runpy,sys
JUDGE_SHA256="e23b3212a0eadc98bc590e5081a92c9fab6740e93808aba2d245d6020b3f8eb0"
def main():
    assert sys.version_info[:2]==(3,11),"Judge requires Python 3.11; never run verdicts on Python 3.12"
    assert sys.version_info[:3]==(3,11,12),"Judge runtime pin requires Python 3.11.12"
    path=pathlib.Path(__file__).with_name("judge_cm3-a3.py")
    assert hashlib.sha256(path.read_bytes()).hexdigest()==JUDGE_SHA256,"Pinned judge bytes changed"
    runpy.run_path(str(path),run_name="__main__")
if __name__=="__main__":main()
