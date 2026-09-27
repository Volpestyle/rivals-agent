from cloud.modal_guard.provider import Provider, billing_values
from cloud.modal_guard.common import IDENTITY
from conftest import raw


def test_month_report_uses_disjoint_days_and_hours(clock, tmp_path):
    commands = []
    class Fake(Provider):
        def identity(self, timeout=10):
            return raw(IDENTITY, clock.wall())
        def _run(self, args, timeout=10):
            commands.append(args)
            if "summary" in args:
                return raw({"metered_cost": "40"}, clock.wall())
            return raw([{"object_id": "ap-one", "interval_start": "2026-09-26T00:00:00"
                         if "d" in args else "2026-09-27T18:00:00", "cost": "2"}], clock.wall())
    value = Fake(wall=clock.wall, billing_root=tmp_path).billing("2026-09")
    assert len(commands) == 3
    assert commands[1][commands[1].index("--end") + 1] == "2026-09-27"
    assert commands[2][commands[2].index("--start") + 1] == "2026-09-27"
    assert commands[1][commands[1].index("--resolution") + 1] == "d"
    assert commands[2][commands[2].index("--resolution") + 1] == "h"
    floor, apps = billing_values(value)
    assert floor == 40 and apps["ap-one"] == 4
