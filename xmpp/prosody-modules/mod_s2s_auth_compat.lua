-- COMPAT for Openfire sending stream headers without to or from.

module:set_global();

module:hook("s2s-check-certificate", function(event)
	local session, host = event.session, event.host;
	if not event.host then
		(session.log or module._log)("warn", "Invalid stream header, certificate will not be trusted")
		session.cert_chain_status = "invalid"
		return true
	end
end, 100);
