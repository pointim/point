#!/usr/bin/env bash

POINT_IS_ALREADY_SETUP=/var/point_is_already_setup

# Создаём папку для исходников и грузим их
get_sources () {
    mkdir -p ${POINT_DIR} && cd ${POINT_DIR}
    mkdir -p log upload img/a/{24,40,80,280} img/m img/t
    chown www-data:www-data -R log upload img

    packages="core www xmpp imgproc stat support"
    for package in ${packages}; do
        clone_repo ${package}
    done
}

clone_repo () {
    local module=$1
    local module_path="${POINT_DIR}/${module}"

    if [ ! -d ${module_path} ]; then
        git clone "https://github.com/artss/point-${module}.git" ${module_path}
        fix_permissions ${module_path}
    fi
}

fix_permissions () {
    chown ${OWNER_ID}:${OWNER_GROUP} -R $1
}

# Устанавливаем зависимости
get_dependencies () {
    cd ${POINT_DIR}
    apt-get install -y --no-install-recommends $(xargs -a core/requirements.apt)
    apt-get clean
    virtualenv --system-site-packages venv
    ./venv/bin/pip install -r core/requirements.pip
}

# Настраиваем нжникс
setup_nginx () {
    cp ${POINT_DIR}/www/etc/nginx/* /etc/nginx/conf.d
    cp ${POINT_DIR}/imgproc/etc/nginx/* /etc/nginx/conf.d
    sed -i -e "s/point\.im/${POINT_DOMAIN}/gm" /etc/nginx/conf.d/*

    # Костыль для старого нжинкса, который не умеет в форматы логов
    sed -i -e "s/ main;/;/m" /etc/nginx/conf.d/10-point.im.conf

    # Удаляем дефолтный сайт
    rm /etc/nginx/sites-enabled/default

    mkdir -p /var/cache/nginx/proxy_cache

    # Генерим ключи для HTTPS
    mkdir -p ${POINT_DIR}/settings/ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -subj "/C=RU/ST=Point" \
        -keyout ${POINT_DIR}/settings/ssl/private.key \
        -out ${POINT_DIR}/settings/ssl/server.crt
}

# Настраиваем базу данных
setup_postgres () {
    POINT_DB_PASSWORD=point

    service postgresql start
    sudo -u postgres createuser -DelERS point
    sudo -u postgres psql -c "ALTER USER point WITH PASSWORD '${POINT_DB_PASSWORD}';"
    sudo -u postgres createdb -e -E utf8 -O point point
    echo "localhost:5432:point:point:${POINT_DB_PASSWORD}" >> /root/.pgpass
    chmod 600 /root/.pgpass

    # Забиваем базу данными
    for schema in ${POINT_DIR}/core/migrations/*; do
        sudo -u postgres psql -f ${schema} point > /dev/null
    done
}

setup_prosody () {
    mkdir -p /var/run/prosody/
    chown prosody:prosody /var/run/prosody/

    # Странный баг в просоди с неправильным именем файла
    sed -i -e "s/localhost.crt/localhost.cert/" /etc/prosody/prosody.cfg.lua

    # Этот не нужен, у нас свой конфиг
    rm /etc/prosody/conf.d/localhost.cfg.lua

    # Добавляем конфиг для нашего сервера
    envsubst < ${SETUP_DIR}/etc/prosody.cfg.lua > /etc/prosody/conf.avail/point.cfg.lua
    ln -s ../conf.avail/point.cfg.lua /etc/prosody/conf.d/
    prosodyctl cert generate ${POINT_DOMAIN}
}

# Пишем конфиги приложения
setup_app () {
    export POINT_BOT_PASSWORD=$(pwgen -c -n -1 12)
    export POINT_DB_PASSWORD=$(awk -F: '{ print $5 }' /root/.pgpass)

    apps="www xmpp imgproc"
    for app in ${apps}; do
        envsubst < ${SETUP_DIR}/settings/${app}.py > ${POINT_DIR}/${app}/settings_local.py
        fix_permissions ${POINT_DIR}/${app}/settings_local.py
    done
}

setup_user () {
    prosodyctl register "${YOUR_USER}" "${POINT_DOMAIN}" "${YOUR_USER}"
    prosodyctl register "p" "${POINT_DOMAIN}" "${POINT_BOT_PASSWORD}"

    psql --user=point --host=localhost --db=point -c \
        "
        INSERT INTO users.logins (id, login, type) VALUES (4, '${YOUR_USER}', 'user');
        INSERT INTO users.accounts (id, user_id, type, address) VALUES (4, 4, 'xmpp', '${YOUR_USER}@${POINT_DOMAIN}');
        "
}

setup_services () {
    cp ${SETUP_DIR}/etc/supervisord.conf /etc/supervisor/supervisord.conf

    update-rc.d prosody disable
    update-rc.d redis-server disable
    update-rc.d postgresql disable

    for service in $(ls ${SETUP_DIR}/etc/supervisor.d/); do
        cp ${SETUP_DIR}/etc/supervisor.d/${service} /usr/local/etc/supervisor.d/${service}
    done
}

if [ -f $POINT_IS_ALREADY_SETUP ]; then
    /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
else
    get_sources
    get_dependencies
    setup_nginx
    setup_postgres
    setup_prosody
    setup_app
    setup_user
    setup_services

    date >> $POINT_IS_ALREADY_SETUP
fi
