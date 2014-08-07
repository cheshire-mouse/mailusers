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

CREATE TABLE `lists` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `listname` varchar(128) NOT NULL,
  `domain` varchar(128) NOT NULL,
  `alias` varchar(255) NOT NULL,
  `goto` varchar(255) NOT NULL,
  UNIQUE KEY `id` (`id`),
  UNIQUE KEY `goto` (`goto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 |

'''
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
    if (value == None):
        return None

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

def dbExec(query,values=None,returnRows=False):
    '''
        executes SQL query
        set returnRows to True if you expect some rows to be returned (SELECT)
        set returnRown to False if you need rowcount to be returned (DELETE,UPDATE)
    '''
    rowcount = 0
    rows = []
    try:
        cnx = mysql.connector.connect(**mysql_config)
        cursor = cnx.cursor()
        if (values == None):
            cursor.execute(query)
        else:
            cursor.execute(query,values)
        if (returnRows):
            for row in cursor:
                rows.append(row)
        else:
            cnx.commit()
            rowcount = cursor.rowcount
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
    if (returnRows):
        return rows
    else:
        return rowcount



def listUsers():
    '''
        print list of existing mailboxes
    '''
    logger.info("list users")
    query = ("SELECT username, domain, quota_limit_bytes, active, description "
            "FROM users ORDER BY domain, username;")
    rows = dbExec(query,returnRows=True)
    print("+-------+---------------------------+----------------------+--------------+----------------------------------------------------+")
    print("| {:^5} | {:^25} | {:^20} | {:^12} | {:<50} |".format("state", "name", "domain", "quota","description"))
    print("+-------+---------------------------+----------------------+--------------+----------------------------------------------------+")
    for (username, domain, quota, active, description) in rows:
        status = '' if (active == 'Y') else 'x'
        print("| {:^5} | {:<25} | {:<20} | {:>12} | {:<50} |".format(status, username, domain, humanReadableSize(quota),description))
    print("+-------+---------------------------+----------------------+--------------+----------------------------------------------------+")

def addMailbox(name,domain,password,description,quota,without_confirm):
    '''
        add mailbox to database
    '''
    if (domain == None):
        domain = defaults["domain"]
    if (quota == None):
        quota = defaults["quota"]
    if (description == None):
        description = defaults["comment"]
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
        print("canceled, exiting")
        return
    logger.info("adding mailbox {}@{} to database".format(name,domain))
    query = ("INSERT INTO users (username, domain, password, description, quota_limit_bytes) "
            " VALUES (%s,%s,%s,%s,%s);")
    values=(name,domain,password_hash,description,quota)
    dbExec(query,values)

def modifyMailbox(address,name=None,domain=None,password=None,description=None,quota=None,without_confirm=False):
    '''
        modify mailbox 
    '''
    if (name != None or domain != None):
        print("\nWARNING! Changing mailbox name or domain will result in "
                "creating new EMPTY mailbox directory, while all messages"
                " will stay in the old one.\n")
    query = ("UPDATE users SET ")
    first = True
    values = {"address" : address}
    for (name,column,value) in [
        ("name","username",name),
        ("domain","domain",domain),
        ("password","password",generateHash(password)),
        ("comment","description", description),
        ("quota","quota_limit_bytes",quota)]:
        if (value == None):
            continue
        if ( not first ):
            query += ", "
        first = False
        query += "{} = %({})s".format(column,name)
        values[name] = value
        print("{:<15} {}".format(name,value))
    if (first):
        logger.info("nothing to change")
        print("nothing to change")
        return
    del password
    query += " WHERE concat(username,'@',domain) = %(address)s; "
    if (not without_confirm and not confirm("Is it OK? (y/n)") ):
        logger.info("canceled, exiting")
        print("canceled, exiting")
        return
    logger.info("changing mailbox {}".format(address))
    logger.debug(query)
    if ( dbExec(query,values) == 0):
        logger.warning("address {} was not found".format(address))


def deleteMailbox(address,without_confirm):
    '''
        delete mailbox from database
    '''
    if (not without_confirm and not confirm("Delete mailbox {}? (y/n)".format(address))):
        logger.info("canceled, exiting")
        print("canceled, exiting")
        return
    logger.info("deleting mailbox {} from database".format(address))
    query = ("DELETE FROM users WHERE concat(username,'@',domain) = %s;")
    values=(address,)
    if ( dbExec(query,values) == 0 ):
        logger.info("nothing to delete: address {} was not found".format(address))
        print("nothing to delete: address {} was not found".format(address))

def changeMailboxActivity(address,disable):
    '''
        suspend/resume mailbox by changing 'active' field in the database 
    '''
    active='Y'
    if (disable):
        logger.info("suspending mailbox {}".format(address))
        active='N'
    else:
        logger.info("resuming mailbox {}".format(address))
    query = ("UPDATE users SET active = %s "
        "WHERE concat(username,'@',domain) = %s;")
    values=(active,address)
    if ( dbExec(query,values) == 0):
        logger.info("nothing to change")
        print("nothing to change")
        
def changeMailboxPassword(address,password):
    '''
        change mailbox password
    '''
    if (password == None):
        password = inputPassword()
    modifyMailbox(address,password=password,without_confirm=True)


def listAliases():
    '''
        print list of existing aliases
    '''
    logger.info("list aliases")
    query = ("SELECT address, goto FROM aliases ORDER BY address, goto;")
    rows = dbExec(query,returnRows=True)
    print("+--------------------------------+--------------------------------+")
    print("| {:<30} | {:<30} |".format("address (alias)","mail to"))
    print("+--------------------------------+--------------------------------+")
    address_prev = None
    for (address,mailto) in rows:
        if (address == address_prev):
            address = ""
        else:
            address_prev = address
        print("| {:<30} | {:<30} |".format(address,mailto))
    print("+--------------------------------+--------------------------------+")

def addAlias(address,mailto,without_confirm):
    '''
        add alias to database
    '''
    print("Creating alias:\n\n"
            "{0} -> {1}\n"
            "".format(address,mailto))
    if (not without_confirm and not confirm("Is it OK? (y/n)") ):
        logger.info("canceled, exiting")
        print("canceled, exiting")
        return
    logger.info("adding alias {} to database".format(address))
    query = ("INSERT INTO aliases (address, goto ) "
            " VALUES (%s,%s);")
    values=(address, mailto)
    dbExec(query,values)

def deleteAlias(address,mailto,without_confirm):
    '''
        delete alias from database
    '''
    if (not without_confirm and 
            not confirm("Delete alias {} -> {}? (y/n)".format(address,mailto))):
        logger.info("canceled, exiting")
        print("canceled, exiting")
        return
    logger.info("deleting alias {} from database".format(address))
    query = ("DELETE FROM aliases WHERE address = %s AND goto = %s;")
    values=(address,mailto)
    if ( dbExec(query,values) == 0 ):
        logger.info("nothing to delete: alias {} -> {} was not found".format(address,mailto))
        print("nothing to delete: alias {} -> {} was not found".format(address,mailto))

def listMaillists():
    '''
        print list of existing maillists
    '''
    logger.info("list maillists")
    query = ("SELECT concat(listname,'@',domain) as maillist "
            "FROM lists "
            "   GROUP BY listname, domain "
            "   ORDER BY domain, listname;")
    rows = dbExec(query,returnRows=True)
    print("+----------------------------------------------------+")
    print("| {:^50} |".format("list name"))
    print("+----------------------------------------------------+")
    for (maillist,) in rows:
        print("| {:<50} |".format(maillist))
    print("+----------------------------------------------------+")

def addMaillist(name,domain,without_confirm):
    '''
        add maillist to database
    '''
    if (domain == None):
        domain = defaults["domain"]
    print("Creating maillist {0}@{1}\n\n"
            "".format(name,domain))
    if (not without_confirm and not confirm("Is it OK? (y/n)") ):
        logger.info("canceled, exiting")
        print("canceled, exiting")
        return
    logger.info("adding maillist {}@{} to database".format(name,domain))
    query = ("INSERT INTO lists (listname, domain, alias, goto) "
            " VALUES ")
    query_tail = ""
    values = ()
    for suffix in ["","-admin","-bounces","-confirm","-join","-leave","-owner","-request","-subscribe","-unsubscribe"]:
        alias_val = name + suffix + "@" + domain
        alias_val_goto = name + suffix + "@lists." + domain
        values += (name,domain,alias_val,alias_val_goto)
        if ( query_tail != "" ):
            query_tail += ","
        query_tail += "(%s,%s,%s,%s)"
    query += query_tail + ";"
    dbExec(query,values)


def deleteMaillist(address,without_confirm):
    '''
        delete maillist from database
    '''
    if (not without_confirm and not confirm("Delete maillist {}? (y/n)".format(address))):
        logger.info("canceled, exiting")
        print("canceled, exiting")
        return
    logger.info("deleting maillist {} from database".format(address))
    query = ("DELETE FROM lists WHERE concat(listname,'@',domain) = %s;")
    values=(address,)
    if ( dbExec(query,values) == 0 ):
        logger.info("nothing to delete: address {} was not found".format(address))
        print("nothing to delete: address {} was not found".format(address))



#logging.basicConfig(level=logging.DEBUG,format="%(asctime)s %(levelname)s %(message)s")
logging.basicConfig(level=logging.WARNING,format="%(levelname)s %(message)s")
logger = logging.getLogger("main")

logger.info("start mailusers.py")
parser = argparse.ArgumentParser(description="Dovecot virtual mailboxes managing tool",
        formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("command",choices=['add','delete','list','modify',"passwd",'disable','enable',
        'addalias','deletealias','listaliases','addlist','deletelist','listlists'],
        help="list - print list of existing mailboxes\n"
            "add - add new mailbox (requires at least '--name' )\n"
            "delete - delete mailbox (requires '--address' option)\n"
            "modify - modify mailbox (requires '--address' option)\n"
            "passwd - change mailbox password (requires '--address' option)\n"
            "disable - disable mailbox (requires '--address' option)\n"
            "enable - enable mailbox (requires '--address' option)\n"
            "listaliases - list existing aliases\n"
            "addalias - add new alias (requires options '--alias'\n"
            "           and '--mailto')\n"
            "deletealias - delete alias (requires options '--alias'\n"
            "           and '--mailto')\n"
            "listlists - list existing maillists\n"
            "addlist - add maillist (requires option '--name')\n"
            "deletelist - delete maillist(requires '--address' option)\n"
            "")
parser.add_argument("--address","-a",help="address of the existing mailbox you want to delete or \n"
        "modify, format is 'username@domain'")
parser.add_argument("--name","-n",help="new name of the mailbox/maillist")
parser.add_argument("--domain","-d",help="mailbox domain")
parser.add_argument("--password","-p",help="mailbox password")
parser.add_argument("--comment","--description","-c",help="short description of the mailbox")
parser.add_argument("--quota","-q",type=int,help="mailbox max size in bytes")
parser.add_argument("-y",action='store_true',default=False,help="answer 'yes' for any stupid question")
parser.add_argument("--alias",help="new alias name")
parser.add_argument("--mailto",help="forward address for new alias")
args = parser.parse_args();

if (args.command == 'list' ):
    listUsers()
elif (args.command == 'add' ):
    if (args.name == None):
        logger.error("Require at least mailbox name ('--name' option) to create anything");
        sys.exit(1);
    addMailbox(args.name,args.domain,args.password,args.comment,args.quota,args.y);
elif (args.command == 'delete' ):
    if (args.address == None):
        logger.error("Require at least mailbox address ('--address' option) to delete anything");
        sys.exit(1);
    deleteMailbox(args.address,args.y)
elif (args.command == 'modify' ):
    if (args.address == None):
        logger.error("Require at least mailbox address ('--address' option) to modify anything");
        sys.exit(1);
    modifyMailbox(args.address,args.name,args.domain,args.password,args.comment,args.quota,args.y);
elif (args.command == 'passwd' ):
    if (args.address == None):
        logger.error("Require at least mailbox address ('--address' option) to change password");
        sys.exit(1);
    changeMailboxPassword(args.address,args.password);
elif (args.command == 'enable' or args.command == 'disable'):
    if (args.address == None):
        logger.error("Require at least mailbox address ('--address' option) to change anything");
        sys.exit(1);
    changeMailboxActivity(args.address,args.command == 'disable')
elif (args.command == 'listaliases' ):
    listAliases()
elif (args.command == 'addalias'):
    if (args.alias == None or args.mailto == None):
        logger.error("Require alias name ('--alias' option) and forward address ('--mailto' option)");
        sys.exit(1);
    addAlias(args.alias,args.mailto,args.y)
elif (args.command == 'deletealias'):
    if (args.alias == None or args.mailto == None):
        logger.error("Require alias name ('--alias' option) and forward address ('--mailto' option)");
        sys.exit(1);
    deleteAlias(args.alias,args.mailto,args.y)
elif (args.command == 'listlists' ):
    listMaillists()
elif (args.command == 'addlist' ):
    if (args.name == None):
        logger.error("Require at least maillist name ('--name' option) to create anything");
        sys.exit(1);
    addMaillist(args.name,args.domain,args.y);
elif (args.command == 'deletelist' ):
    if (args.address == None):
        logger.error("Require at least maillist address ('--address' option) to delete anything");
        sys.exit(1);
    deleteMaillist(args.address,args.y)


logger.info("finish mailusers.py")


