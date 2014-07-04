#! /usr/bin/python3

'''
mailusers.py
Dovecot virtual mailboxes managing tool (mysql)

$Id$
license: WTFPL v2
'''

# toDo: command list
# toDo: command add
# toDo: command delete
# toDo: command modify
# toDo: command suspend
# toDo: command resume
# toDo: command listaliases
# toDo: command addalias
# toDo: command deletealias

import logging
import argparse
import mysql.connector
from mysql.connector import errorcode

from mailusers_config import mysql_config

def listUsers():
    logger.info("list users")
    try:
        cnx = mysql.connector.connect(**mysql_config)
        cursor = cnx.cursor()
        query = ("SELECT username, domain, quota_limit_bytes, active FROM users;")
        cursor.execute(query)
        print("+-------+---------------------------+----------------------+--------------+")
        print("| {:^5} | {:^25} | {:^20} | {:^12} |".format("on", "user", "domain", "quota"))
        print("+-------+---------------------------+----------------------+--------------+")
        units = ["b ", "Kb", "Mb", "Gb", "Tb"]
        for (username, domain, quota, active) in cursor:
            u = 0
            while (quota / 1024 >= 1):
                u += 1
                quota /=1024
            if (active == 'Y'):
                active = '+'
            else:
                active = ''
            print("| {:^5} | {:<25} | {:<20} | {:>10.1f}{} |".format(active, username, domain, quota, units[u]))
        print("+-------+---------------------------+----------------------+--------------+")
        cursor.close()
        cnx.close()
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error("Database does not exists")
        else:
            logger.error(err)
    else:
        cnx.close()


logging.basicConfig(level=logging.DEBUG,format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("main")

logger.info("start mailusers.py")
parser = argparse.ArgumentParser(description="Dovecot virtual mailboxes managing tool")
parser.add_argument("command",choices=['add','delete','list','modify','suspend','resume','addalias','deletealias','listaliases'])
args = parser.parse_args();
if (args.command == 'list' ):
    listUsers()
logger.info("finish mailusers.py")
