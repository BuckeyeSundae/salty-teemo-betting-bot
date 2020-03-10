"""
Performs some basic analysis on the sqltable saved in lib.
"""
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt


def math_them_stats():
    return


def main():
    conn = sqlite3.connect("lib\\salty_hist.sqlite")
    cur = conn.cursor()
    try:
        df = pd.read_sql_query("Select bet_ratio, win_status, bet_side, ID "
                               "from BalanceRecord "
                               "where bet_ratio is not null", conn, index_col='ID')
        total = df['bet_ratio'].where(df['win_status'] == 1).count()
        totalgames = df['win_status'].where(df['win_status'] == 1).count()
        print(total)
        print(totalgames)
        df['loss_predicts'] = df['bet_ratio'].where(df['win_status'] < 1)
        df['win_predicts'] = df['bet_ratio'].where(df['win_status'] == 1)
    except:
        cur.close()
        conn.close()
        raise


if __name__ == "__main__":
    main()
