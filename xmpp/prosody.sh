#!/bin/bash

chown prosody . -R

if [ "$XMPP_BOT_USERNAME" -a  "$XMPP_BOT_DOMAIN" -a "$XMPP_BOT_PASSWORD" ] ; then
  domain=$(echo -n $XMPP_BOT_DOMAIN | sed 's/\./%2e/g')
  if [ ! -f "/var/lib/prosody/$domain/accounts/$XMPP_BOT_USERNAME.dat" ] ; then
    echo "Registering xmpp bot JID: $XMPP_BOT_USERNAME@$XMPP_BOT_DOMAIN"
    prosodyctl register $XMPP_BOT_USERNAME $XMPP_BOT_DOMAIN $XMPP_BOT_PASSWORD
  else
    echo "Skipping xmpp bot JID registration: $XMPP_BOT_USERNAME@$XMPP_BOT_DOMAIN"
  fi
fi

sudo -u prosody /usr/bin/luajit /usr/bin/prosody

