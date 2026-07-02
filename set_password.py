"""CLI: задать/сбросить пароль пользователя.

Использование:
    python set_password.py <username> <new_password>
"""
import sys

from auth import set_password
from db import query_one


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    user = query_one('SELECT id FROM users WHERE username = %s', (username,))
    if not user:
        print(f'Пользователь "{username}" не найден в таблице users.')
        sys.exit(1)

    set_password(username, password)
    print(f'Пароль пользователя "{username}" обновлён.')


if __name__ == '__main__':
    main()
