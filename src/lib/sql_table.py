"""
This file will create a sqlite database in your local environment at the specified location. This is to save balances
    and run comparisons over time.
"""
import pony.orm as po
from datetime import datetime

db = po.Database()


class BalanceRecord(db.Entity):
    ID = po.PrimaryKey(int, auto=True)
    time = po.Required(datetime, default=datetime.utcnow(), unique=True)
    farm_event = po.Optional(bool, default=False)
    starting_balance = po.Optional(int)
    win_status = po.Optional(bool)
    bet_amt = po.Optional(int)
    bet_side = po.Optional(str)
    favored_side = po.Optional(str)
    bet_ratio = po.Optional(float)
    new_balance = po.Optional(int)


po.set_sql_debug(False)
db.bind(provider="sqlite", filename="salty_hist.sqlite", create_db=True)
db.generate_mapping(create_tables=True)
po.commit()
