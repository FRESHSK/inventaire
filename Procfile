web: python manage.py collectstatic --noinput && python manage.py migrate --noinput && gunicorn config.wsgi --log-file - --bind 0.0.0.0:$PORT
