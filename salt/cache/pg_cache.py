# -*- coding: utf-8 -*-
'''
Cache plugin for PostgreSQL database.

Usage:

To use the `pg_cache` cache interface:

.. code-block:: yaml

    cache: pg_cache

Available configurations for `pg_cache` cache interface:

.. code-block:: yaml

    cache.postgres.host: 127.0.0.1
    cache.postgres.port: 5432
    cache.postgres.user: 'salt'
    cache.postgres.passwd: 'salt'
    cache.postgres.db: 'salt_cache'
    mysql.table_name: cache

Dependencies: 

The PostgreSQL server must be 9.5 or later to accommodate proper upserting.

The `psycopg2-binary` library must be installed on the master:

.. code-block:: bash

    pip install psycopg2-binary

The following database schema must be in place before `pg_cache` can function correctly:

.. code-block:: sql

    CREATE DATABASE  salt
      WITH ENCODING 'utf-8';

    DROP TABLE IF EXISTS cache;
    CREATE TABLE IF NOT EXISTS cache (
        bank    varchar(255) NOT NULL,
        key     varchar(255) NOT NULL,
        data    jsonb NOT NULL);

    CREATE UNIQUE INDEX idx_cache_i ON cache (bank, key);
    CREATE INDEX idx_cache_bank ON cache (bank);
    CREATE INDEX idx_cache_key ON cache (key);
    CREATE INDEX idx_cache_data ON cache USING gin(data);
'''
from __future__ import absolute_import, print_function, unicode_literals

import logging
from contextlib import contextmanager

import salt.exceptions
import salt.serializers.json
from salt.ext import six

try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

log = logging.getLogger(__name__)

__virtualname__ = 'pg_cache'
__func_alias__ = {'list_': 'list'}


def __virtual__():
    '''
    Confirm that a psycopg2 client is installed.
    '''
    if not HAS_POSTGRES:
        return (False, 'Could not import postgres returner; psycopg2 is not installed.')
    return __virtualname__


def init_kwargs(kwargs):
    return {}


@contextmanager
def _exec_pg(commit=False):
    '''
    pg context manager
    '''
    port = __opts__.get('cache.postgres.port', 5432)
    if not isinstance(port, six.integer_types):
        port = int(port)

    try:
        conn = psycopg2.connect(
               host= __opts__.get('cache.postgres.host', 'localhost'),
               port= __opts__.get('cache.postgres.port', 5432),
               user= __opts__.get('cache.postgres.user', 'salt'),
               password= __opts__.get('cache.postgres.passwd', 'salt'),
               database= __opts__.get('cache.postgres.db', 'salt'))
                
    except psycopg2.OperationalError as exc:
        raise salt.exceptions.SaltMasterError('postgres returner could not connect to database: {exc}'.format(exc=exc))

    cursor = conn.cursor()

    log.debug("pg_cache connected to psql server ...")
    try:
        yield cursor
    except psycopg2.DatabaseError as err:
        error = err.args
        log.error(six.text_type(error))
        cursor.execute("ROLLBACK")
        raise err
    else:
        if commit:
            cursor.execute("COMMIT")
        else:
            cursor.execute("ROLLBACK")
    finally:
        conn.close()


def store(bank, key, data):
    '''
    Store a key value.
    '''
    store_sql = """INSERT INTO cache
                   (bank, key, data)
                   VALUES(%s, %s, %s)
                   ON CONFLICT (bank, key) DO UPDATE
                   SET data=EXCLUDED.data"""

    log.debug("pg_cache storing %s:%s:%s", bank, key, data)
    try:
        with _exec_pg(commit=True) as cur:
            cur.execute(store_sql,
                        (bank, key, psycopg2.extras.Json(data))
            )
    except salt.exceptions.SaltMasterError:
        log.critical('Could not store cache with postgres cache. PostgreSQL server unavailable.')


def fetch(bank, key):
    '''
    Fetch a key value.
    '''
    fetch_sql = """SELECT data 
                   FROM cache 
                   WHERE bank=%s AND key=%s"""

    try:
        with _exec_pg() as cur:
            cur.execute(fetch_sql, (bank, key))
            data = cur.fetchone()
            if data:
                return data[0]
            return {}
    except salt.exceptions.SaltMasterError:
        log.critical('Could not fetch cache with postgres cache. PostgreSQL server unavailable.')


def flush(bank, key=None):
    '''
    Remove the key from the cache bank with all the key content.
    '''
    params = [bank]
    del_sql = """DELETE FROM cache
                 WHERE bank=%s"""

    if key is not None:
        del_sql += " AND key=%s"
        params.append(key)

    log.debug("pg_cache flushing %s:%s", bank, key)
    try:
        with _exec_pg(commit=True) as cur:
            cur.execute(del_sql, params)
    except psycopg2.DatabaseError as err:
        cursor.execute("ROLLBACK")
        log.critical(err.args)
    except salt.exceptions.SaltMasterError:
        log.critical('Could not flush cache with postgres cache. PostgreSQL server unavailable.')


def list_(bank):
    '''
    Return an iterable object containing all entries stored in the specified
    bank.
    '''
    ls_sql = """SELECT key
                FROM cache
                WHERE bank=%s"""

    log.debug("pg_cache listing %s", bank)
    try:
        with _exec_pg() as cur:
            cur.execute(ls_sql, (bank,))
            data = cur.fetchall()
            if data:
                return data
            return {}
    except salt.exceptions.SaltMasterError:
        log.critical('Could not list cache with postgres cache. PostgreSQL server unavailable.')


def contains(bank, key):
    '''
    Checks if the specified bank contains the specified key.
    '''
    in_sql = """SELECT COUNT(data)
                FROM cache
                WHERE bank=%s
                AND key=%s"""
   
    log.debug("pg_cache check if %s in %s", key, bank)
    try:
        with _exec_pg() as cur:
            cur.execute(in_sql, (bank,key))
            data = cur.fetchone()
            if (len(data) > 0) and data[0] == 1:
                return True
            return False
    except salt.exceptions.SaltMasterError:
        log.critical('Could not run contains with postgres cache. PostgreSQL server unavailable.')
