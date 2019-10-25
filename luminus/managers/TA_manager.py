from luminus import sql_helper


def get_TA_by_username(username):
    return sql_helper.fetchall_to_dict("SELECT name, email FROM Users NATURAL JOIN TAs"
                                       " WHERE uname = %(username)s", {'username': username})


def get_TAs_by_coursecode(code):
    return sql_helper.fetchall_to_dict("SELECT name, major, email FROM Users NATURAL JOIN ((TAs NATURAL JOIN Participators) NATURAL JOIN Assist)"
                                       " WHERE code = %(code)s", {'code': code})


def get_TAs_by_coursecode_and_groupnum(code, group_num):
    return sql_helper.fetchall_to_dict("SELECT name, email FROM Users NATURAL JOIN (TAs NATURAL JOIN Facilitate)"
                                       " WHERE code = %(code)s AND group_num = %(group)s",
                                       {'code': code, 'group_num': group_num})
