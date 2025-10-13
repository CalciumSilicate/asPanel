from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class ConfigObject:
    type: Any
    value: Any
    desc: str


def _gen_obj(_type, value, *desc: str) -> ConfigObject:
    return ConfigObject(_type, value, " ".join(desc) if desc else "")


SERVER_CONFIGURATION = {
    "via_version": [
        {
            "title": "Via Version",
            "name": "Via Version",
            "path": [{"type": "yml", "path": "server/plugins/viaversion/config.yml"}],
            "server_type": ["velocity", "bungeecord"],
            "needs": [{"type": "mc_plugin", "id": "viaversion", "source": ["modrinth"]}],
            "loader": [],
            "default": [
                {
                    "max-pps": _gen_obj(
                        int, 800, "(suggest to set a large number) max packets per seconds,",
                        "that if you exceeds you will get kicked instantly"
                    ),
                    "tracking-warning-pps": _gen_obj(
                        int, 120, "(suggest to set a large number) warning packets per seconds, that",
                        "if you exceeds over 'tracking-max-warnings' times you will get kicked instantly"
                    ),
                    "tracking-max-warnings": _gen_obj(int, 4, "max warning count")
                }
            ]
        }
    ],
    "velocity_proxy": [
        {
            "title": "Velocity Proxy",
            "name": "Fabric Proxy Lite",
            "path": [{"type": "toml", "path": "server/config/FabricProxy-Lite.toml"}],
            "server_type": ["vanilla"],
            "needs": [{"type": "mod", "id": "fabricproxy-lite", "source": ["modrinth", "curseforge"]}],
            "loader": ["fabric"],
            "default": [
                {
                    "hackOnlineMode": _gen_obj(
                        bool, True, "Allows connection through a proxy without disabling online-mode."
                    ),
                    "hackEarlySend": _gen_obj(
                        bool, False, "Fabric-API can't send packet before QUERY_START event,",
                        "so player info(UUID) will not ready at QUERY_START event. Setting",
                        "hackEarlySend to true will use mixin for early send packet to velocity.",
                        "This is required for some mods, such as LuckPerms."
                    ),
                    "hackMessageChain": _gen_obj(
                        bool, False, "(suggest to set True) This option fixes players being kicked for",
                        "Received chat packet with missing or invalid signature. or Chat message",
                        "validation failure, which only happens when the player switches to another server."
                    ),
                    "disconnectMessage": _gen_obj(
                        str, "This server requires you to connect with Velocity.",
                        "The custom disconnect/kick message for users that aren't connecting through Velocity."
                    ),
                    "secret": _gen_obj(
                        str, "",
                        "The Velocity forwarding secret. This should be the same",
                        "random string as in Velocity's forwarding.secret file."
                    )
                }

            ]
        }
    ],
    "prime_backup": [
        {
            "title": "Prime Backup",
            "name": "Prime Backup",
            "path": [{"type": "json", "path": "config/prime_backup/config.json"}],
            "server_type": ["*"],
            "needs": [{"type": "mcdr_plugin", "id": "prime_backup", "source": ["plugin_catalogue", "db_plugins"]}],
            "loader": ["*"],
            "default": [
                {
                    "enabled": _gen_obj(bool, False),
                    "command": {"permission": {"back": _gen_obj(int, 2,
                                                                "Least permission that a user need to back. 0-4 for guest, user(default), helper, admin, owner")}},
                    "scheduled_backup": {
                        "enabled": _gen_obj(bool, False),
                        "interval": _gen_obj(str, "12h"),
                        "crontab": _gen_obj(str, None),
                        "require_online_players": _gen_obj(bool, False),
                        "require_online_players_backlist": _gen_obj(List, [])
                    },
                    "prune": {
                        "enabled": _gen_obj(bool, True),
                    },
                }
            ]
        }
    ],
    "auto_plugin_reloader": [
        {
            "title": "Auto Plugin Reloader",
            "name": "Auto Plugin Reloader",
            "path": [{"type": "json", "path": "config/auto_plugin_reloader/config.json"}],
            "server_type": ["*"],
            "needs": [
                {"type": "mcdr_plugin", "id": "auto_plugin_reloader", "source": ["plugin_catalogue", "db_plugins"]}
            ],
            "loader": ["*"],
            "default": [
                {
                    "enabled": _gen_obj(bool, True),
                    "permission": _gen_obj(int, 4),
                    "detection_interval_sec": _gen_obj(int, 5),
                    "reload_delay_sec": _gen_obj(float, 0.5),
                    "blacklist": _gen_obj(List, [])
                }
            ]
        }
    ],
    "bili_live_helper": [
        {
            "title": "Bili Live Helper",
            "name": "Bili Live Helper",
            "path": [{"type": "json", "path": "config/bili_live_helper/config.json"}],
            "server_type": ["*"],
            "needs": [{"type": "mcdr_plugin", "id": "bili_live_helper", "source": ["plugin_catalogue", "db_plugins"]}],
            "loader": ["*"],
            "default": [
                {
                    "enable": _gen_obj(bool, True, "Enable or disable this entire feature."),
                    "account": {
                        "uid": _gen_obj(int, 0, "Your Bilibili User ID (UID)."),
                        "sessdata": _gen_obj(str, "", "Your SESSDATA cookie value for authentication."),
                        "bili_jct": _gen_obj(str, "", "Your bili_jct cookie value, used for CSRF protection."),
                        "buvid3": _gen_obj(str, "", "Your buvid3 cookie value, acts as a device identifier."),
                        "ac_time_value": _gen_obj(str, "", "Your ac_time_value cookie value, related to access time.")
                    }
                }

            ]
        }
    ],
    "where_is": [
        {
            "title": "Where Is",
            "name": "Where Is",
            "path": [{"type": "json", "path": "config/where_is/config.json"}],
            "server_type": ["*"],
            "needs": [{"type": "mcdr_plugin", "id": "where_is", "source": ["plugin_catalogue", "db_plugins"]}],
            "loader": ["*"],
            "default": [
                {
                    "enable_here": _gen_obj(bool, True, "Enable the 'here' command functionality."),
                    "enable_where_is": _gen_obj(bool, True, "Enable the 'where_is' command functionality."),
                    "command_prefix": {
                        "where_is": _gen_obj(list, [
                            "!!vris",
                            "!!whereis",
                            "!!where"
                        ], "List of command prefixes/aliases for the 'where_is' command."),
                        "here": _gen_obj(list, [
                            "!!here"
                        ], "List of command prefixes/aliases for the 'here' command.")
                    },
                    "highlight_time": {
                        "where_is": _gen_obj(int, 0,
                                             "Highlight duration in seconds for the 'where_is' command's result. 0 means no highlight."),
                        "here": _gen_obj(int, 15, "Highlight duration in seconds for the 'here' command's result.")
                    }
                }

            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ],
    "ID": [
        {
            "title": "TITLE",
            "name": "NAME",
            "path": [{"type": "TYPE", "path": "PATH"}],
            "server_type": ["*"],
            "needs": [{"type": "TYPE", "id": "ID", "source": []}],
            "loader": ["*"],
            "default": [
            ]
        }
    ]
}
