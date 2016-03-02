VirtualHost "${POINT_DOMAIN}"
	modules_disabled = { "s2s" }
	allow_registration = true
	ssl = {
		key = "/var/lib/prosody/${POINT_DOMAIN}.key";
		certificate = "/var/lib/prosody/${POINT_DOMAIN}.crt";
	}
