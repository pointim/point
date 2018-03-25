
local s2smanager = require "core.s2smanager";
local config = require "core.configmanager";
local nameprep = require "util.encodings".stringprep.nameprep;

local s2s_blacklist = module:get_option_array("s2s_blacklist");
local s2s_whitelist = module:get_option_array("s2s_whitelist");
local s2s_enable_blackwhitelist = module:get_option_string("s2s_enable_blackwhitelist");
local is_blacklist_enabled = false;
local is_whitelist_enabled = false;

if s2s_enable_blackwhitelist == "blacklist" then
	if type(s2s_blacklist) == "table" then
		is_blacklist_enabled = true;
		module:log("debug", "s2s-blacklist is enabled");
		local count=#s2s_blacklist;
                for i=1,count do
			module:log("debug", "s2s-blacklist adding [%s]", s2s_blacklist[i]);
		end
	end
elseif s2s_enable_blackwhitelist == "whitelist" then
	if type(s2s_whitelist) == "table" then
		is_whitelist_enabled = true;
		module:log("debug", "s2s-whitelist is enabled");
                local count=#s2s_whitelist;
                for i=1,count do
                        module:log("debug", "s2s-whitelist adding [%s]", s2s_whitelist[i]);
                end
	end
end

local function reload_list()
	s2s_blacklist = module:get_option_array("s2s_blacklist");
	s2s_whitelist = module:get_option_array("s2s_whitelist");
	s2s_enable_blackwhitelist = module:get_option_string("s2s_enable_blackwhitelist");

	if s2s_enable_blackwhitelist == "blacklist" then
        	if type(s2s_blacklist) == "table" then
                	is_blacklist_enabled = true;
                	module:log("debug", "s2s-blacklist is enabled");
                	local count=#s2s_blacklist;
                	for i=1,count do
                        	module:log("debug", "s2s-blacklist adding [%s]", s2s_blacklist[i]);
                	end
        	end
	elseif s2s_enable_blackwhitelist == "whitelist" then
        	if type(s2s_whitelist) == "table" then
                	is_whitelist_enabled = true;
                	module:log("debug", "s2s-whitelist is enabled");
                	local count=#s2s_whitelist;
                	for i=1,count do
                        	module:log("debug", "s2s-whitelist adding [%s]", s2s_whitelist[i]);
                	end
        	end
	end
end

local _make_connect = s2smanager.make_connect;
function s2smanager.make_connect(session, connect_host, connect_port)
  local host = session.to_host;
  if not session.s2sValidation then
        if (host and is_blacklist_enabled == true) then
                local count=#s2s_blacklist;
                for i=1,count do
                        if s2s_blacklist[i] == host then
                                module:log ("error", "blacklisted host received %s", s2s_blacklist[i]);
                                s2smanager.destroy_session(session, "This host does not serve "..host);
                                return false;
                        end
                end
        elseif (host and is_whitelist_enabled == true)  then
                local count=#s2s_whitelist;
                local found=false;
                for i=1,count do
                        if s2s_whitelist[i] == host then
                                found=true;
                        end
                end
                if found == false then
                        module:log ("error", "host %s couldn't be found in whitelist", host);
                        s2smanager.destroy_session(session, "This host does not serve "..host);
                        return false;
                end
        end
  end
  return _make_connect(session, connect_host, connect_port);
end

local _stream_opened = s2smanager.streamopened;
function s2smanager.streamopened(session, attr)
        local host = attr.from and nameprep(attr.from);
        if not host then
                session.s2sValidation = false;
        else
                session.s2sValidation = true;
        end

        if (host and is_blacklist_enabled == true) then
                local count=#s2s_blacklist;
                for i=1,count do
                        if s2s_blacklist[i] == host then
                                module:log ("error", "blacklisted host received %s", s2s_blacklist[i]);
                                session:close({condition = "host-unknown", text = "This host does not serve " .. host});
                                return;
                        end
                end
        elseif (host and is_whitelist_enabled == true)  then
                local count=#s2s_whitelist;
                local found=false;
                for i=1,count do
                        if s2s_whitelist[i] == host then
                                found=true;
                        end
                end
                if found == false then
                        module:log ("error", "host %s couldn't be found in whitelist", host);
                        session:close({condition = "host-unknown", text = "This host does not serve " .. host});
                        return;
                end
        end
        _stream_opened(session, attr);
end


local function server_dialback_result_hook (event)
	local origin, stanza = event.origin, event.stanza;

	if origin.type == "s2sin" or origin.type == "s2sin_unauthed" then

		local host = stanza.attr.from;

		if (host and is_blacklist_enabled == true) then
			local count=#s2s_blacklist;
			for i=1,count do
 				if s2s_blacklist[i] == host then
					module:log ("error", "blacklisted host received %s", s2s_blacklist[i]);
      					origin:close({condition = "host-unknown", text = "This host does not serve " .. host});
					return true;
				end
			end
		elseif (host and is_whitelist_enabled == true)  then
			local count=#s2s_whitelist;
			local found=false;
			for i=1,count do
				if s2s_whitelist[i] == host then
					found=true;
				end
			end
			if found == false then
				module:log ("error", "host %s couldn't be found in whitelist", host);
      				origin:close({condition = "host-unknown", text = "This host does not serve " .. host});
				return true;
			end
		end
	
	end

	return nil;
end

local function handle_activated_host (host)
        if (hosts[host] and hosts[host].events) then
                hosts[host].events.add_handler("stanza/jabber:server:dialback:result", server_dialback_result_hook, 100);
                module:log ("debug", "adding hook for %s", host);
        end
end

local function handle_deactivated_host (host)
        if (hosts[host] and hosts[host].events) then
                hosts[host].events.remove_handler("stanza/jabber:server:dialback:result", server_dialback_result_hook);
                module:log ("debug", "removing hook for %s", host);
        end
end

prosody.events.add_handler("host-activated", handle_activated_host);
prosody.events.add_handler("component-activated", handle_activated_host);
prosody.events.add_handler("host-deactivated", handle_deactivated_host);
prosody.events.add_handler("component-deactivated", handle_deactivated_host);
prosody.events.add_handler("config-reloaded", reload_list);

for name, host in pairs(hosts) do
	if host and host.events then
		host.events.add_handler("stanza/jabber:server:dialback:result", server_dialback_result_hook, 100);
                module:log ("debug", "adding hook for %s", name);
	end
end

