admins = {"arts@psto.net", "arts@point.im" }

use_libevent = true;

modules_enabled = {
  "roster";
  "saslauth";
  "tls";
  "dialback";
  "disco";

  "private";
  "vcard";

  "legacyauth";
  "ping";
  "pep";
  "register";
  "adhoc";

  "admin_adhoc";
  "admin_telnet";

  "posix";

  "s2s_blackwhitelist"; -- http://code.google.com/p/prosody-modules/wiki/mod_s2s_blackwhitelist
  "s2s_auth_compat"; -- for ya.ru
};

modules_disabled = {
};

allow_registration = false;

-- s2s blacklisting
s2s_enable_blackwhitelist = "blacklist"
s2s_blacklist = { "gomorra.dyndns-remote.com" }

authentication = "internal_plain"

log = {
  {levels = {min = "info"}, to = "console"};
}

daemonize = false;

VirtualHost "point.im"
  ssl = {
    key = "/home/point/ssl/server.key";
    certificate = "/home/point/ssl/server.crt";
  }

