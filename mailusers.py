#! /usr/bin/python3

'''
mailusers.py
Dovecot virtual mailboxes managing tool (mysql)

$Id$
license: WTFPL v2
'''
'''
requires following mysql tables:

CREATE TABLE `users` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(128) NOT NULL,
  `password` varchar(128) NOT NULL,
  `active` char(1) NOT NULL DEFAULT 'Y',
  `domain` varchar(128) NOT NULL,
  `quota_limit_bytes` bigint(20) unsigned NOT NULL DEFAULT '104857600',
  `description` varchar(256) NOT NULL DEFAULT '',
  UNIQUE KEY `id` (`id`),
  UNIQUE KEY `username` (`username`,`domain`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8 

CREATE TABLE `aliases` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `address` varchar(255) NOT NULL,
  `goto` varchar(255) NOT NULL,
  UNIQUE KEY `id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8
'''
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

import sys
import getpass
import base64
import hashlib
import random
 

from mailusers_config import mysql_config

defaults = {
    'domain' : 'heewie.org',
    'comment' : '-',
    'quota' : 1024*1024*1024
}

def humanReadableSize(value):
    '''
        converts size in bytes into more user friendly string
    '''
    units = ["b ", "Kb", "Mb", "Gb", "Tb"]
    u = 0
    divisor = 1024
    while (value / divisor >= 1):
        u += 1
        divisor *= 1024
    divisor /= 1024
    return "{:.1f} {}".format(value/divisor,units[u])

def generateHash(value):
    '''
        generate SSHA-512 hash suitable for Dovecot

        this code belongs to mr Guest: http://pastebin.com/xD4qWzBG
        thanks, dude
    '''

    salt = ''.join([chr(random.randrange(0, 256)) for x in range(0,8)])
     
    bValue = value.encode('utf-8')
    bSalt = salt.encode('utf-8')

    return '{SSHA512}' + (base64.b64encode(hashlib.sha512(bValue+bSalt).digest()+bSalt)).decode('utf-8') 

def inputPassword():
    '''
        make user give away his password
        muahahaha!
    '''
    logger.info("input password")
    password = None
    while (password == None):
        password=getpass.getpass()
        password_confirm=getpass.getpass('Retype password: ')
 
        if(password != password_confirm):
            print('Password do not match.')
            password = None
    return password

def confirm(message):
    '''
        make user confirm something
    '''
    print(message)
    answer = input()
    if ( answer.lower() == 'y' ):
        return True
    else :
        return False


def listUsers():
    '''
        print list of existing mailboxes
    '''
    logger.info("list users")
    try:
        cnx = mysql.connector.connect(**mysql_config)
        cursor = cnx.cursor()
        query = ("SELECT username, domain, quota_limit_bytes, active, description FROM users;")
        cursor.execute(query)
        print("+-------+---------------------------+----------------------+--------------+----------------------------------------------------+")
        print("| {:^5} | {:^25} | {:^20} | {:^12} | {:<50} |".format("on", "name", "domain", "quota","description"))
        print("+-------+---------------------------+----------------------+--------------+----------------------------------------------------+")
        for (username, domain, quota, active, description) in cursor:
            if (active == 'Y'):
                active = '+'
            else:
                active = ''
            print("| {:^5} | {:<25} | {:<20} | {:>12} | {:<50} |".format(active, username, domain, humanReadableSize(quota),description))
        print("+-------+---------------------------+----------------------+--------------+----------------------------------------------------+")
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

def addMailbox(name,domain,password,description,quota,without_confirm):
    '''
        add mailbox to database
    '''
    if (password == None):
        password = inputPassword()
    password_hash = generateHash(password)
    del password
    print("Creating mailbox with the following option:\n\n"
            "name:\t\t{0}\ndomain:\t\t{1}\nquota:\t\t{4}\n"
            "comment:\t{3}\npassword:\t{2}\n\n"
            "".format(name,domain,password_hash,description,humanReadableSize(quota)))
    if (not without_confirm and not confirm("Is it OK? (y/n)") ):
        logger.info("canceled, exiting")
        return
    logger.info("adding mailbox {}@{} to database".format(name,domain))
    try:
        cnx = mysql.connector.connect(**mysql_config)
        cursor = cnx.cursor()
        query = ("INSERT INTO users (username, domain, password, description, quota_limit_bytes) "
                " VALUES (%s,%s,%s,%s,%s);")
        values=(name,domain,password_hash,description,quota)
        cursor.execute(query,values)
        cnx.commit()
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
parser = argparse.ArgumentParser(description="Dovecot virtual mailboxes managing tool",
        formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("command",choices=['add','delete','list','modify','suspend','resume','addalias','deletealias','listaliases'],
        help="list - print list of existing mailboxes\n"
            "add - add new mailbox (require at least '--name' option)")
parser.add_argument("--name","-n",help="name of the mailbox")
parser.add_argument("--domain","-d",default=defaults["domain"],help="mailbox domain")
parser.add_argument("--password","-p",help="mailbox password")
parser.add_argument("--comment","--description","-c",default=defaults["comment"],help="short description of the mailbox")
parser.add_argument("--quota","-q",type=int,default=defaults["quota"],help="mailbox max size in bytes")
parser.add_argument("-y",action='store_true',default=False,help="answer 'yes' for any stupid question")
args = parser.parse_args();
if (args.command == 'list' ):
    listUsers()
elif (args.command == 'add' ):
    if (args.name == None):
        logger.error("Require at least mailbox name ('--name' option) to create something");
        sys.exit(1);
    addMailbox(args.name,args.domain,args.password,args.comment,args.quota,args.y);
logger.info("finish mailusers.py")


