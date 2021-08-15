import appdaemon.plugins.hass.hassapi as hass

"""
@OptimusGREEN

example usage

dmx_restore:                                                    # [required: name of your app]
  module: dmx_mqtt_restore                                      # [required: py file name]
  class: DmxMqttRestore                                         # [required: class used from the module]
  topic_prefix: "mydmxtopicprefix"                              # [optional: default "dmx"]
  include: ["light.dmxlight1", "light.dmxlight2"]          # [optional: list: list of dmx light entity_id's]
  exclude: ["light.non_dmxlight1", "light.non_dmxlight2"]  # [optional: list: list of NON dmx light entity_id's]
  
  dont use both include and exclude at same time. 
  Either include your dmx lights or exclude your non dmx lights
  If all your lights are dmx then just dont use any list as it will do all lights by default.
  
"""

class DmxMqttRestore(hass.Hass):

    def initialize(self):

        self.debug_mode = True
        self.restored = False

        self.topics = []
        self.light_dicts = []

        if "topic_prefix" in self.args:
            self.prefix = self.args["topic_prefix"]
        else:
            self.prefix = "dmx"

        if "include" and "exclude" in self.args:
            raise Exception("Both 'include' and 'exclude' were used. Only one or the other is allowed")
        elif "include" in self.args:
            self.lights = self.args["include"]
            self._populate_include()
        elif "exclude" in self.args:
            self.lights = self.args["exclude"]
            self._populate_exclude()
        else:
            self.lights = []
            self._populate_exclude()

        self.listen_event(self._restore_state_from_mqtt, "MQTT_MESSAGE", namespace="mqtt")

        for light in self.light_dicts:
            self.listen_state(self._publish_state, entity=light["name"], attribute="brightness")

    def logme(self, string, level="info", *args, **kwargs):
        if level == "debug":
            if self.debug_mode:
                import inspect
                frame = inspect.currentframe().f_back
                line = "Line: " + str(frame.f_lineno)
                self.log("[{}] - {}".format(line, string))
        else:
            self.log(string)

    def _restore_state_from_mqtt(self, event_name, data, *args, **kwargs):
        if not self.restored:
            topic = data["topic"]
            self.logme("topic: {}".format(topic), level="debug")
            if topic in self.topics:
                self.logme(data, level="debug")
                for light in self.light_dicts:
                    if light["topic"] == topic:
                        brightness = data["payload"]
                        self.logme(brightness)
                        self._set_state(entity=light["name"], brightness=light["level"])
            self.restored = True

    def _populate_include(self, *args, **kwargs):
        self.logme("", level="debug")
        for light in self.lights:
            self._build_light_dict(light)

    def _populate_exclude(self, *args, **kwargs):
        self.logme("", level="debug")
        for light in self.get_state("light"):
            if light not in self.lights:
                self._build_light_dict(light)


    def _build_light_dict(self, light, *args, **kwargs):
        self.logme("light: {}".format(light), level="debug")
        data = self.get_state(entity_id=light, attribute="all")
        self.logme("data: {}".format(data), level="debug")
        dict = {}
        dict["name"] = data["entity_id"]
        dict["state"] = data["state"]
        if dict["state"] == "on" and "brightness" in data:
            dict["level"] = data["attributes"]["brightness"]
        else:
            dict["level"] = 0
        dict["universe"] = data["attributes"]["dmx_universe"]
        dict["channel"] = data["attributes"]["dmx_channels"][0]
        dict["topic"] = "{}/{}/{}".format(self.prefix,
                                          data["attributes"]["dmx_universe"],
                                          data["attributes"]["dmx_channels"][0])
        self.light_dicts.append(dict)
        self.topics.append(dict["topic"])

    def _publish_state(self, entity_id, *args, **kwargs):
        self.logme("entity_id: {}".format(entity_id), level="debug")
        for light in self.light_dicts:
            if light["name"] == entity_id:
                topic = light["topic"]
                state = self.get_state(light["name"])
                if state == "off":
                    level = 0
                else:
                    level = self.get_state(light["name"], attribute="brightness")
                self.call_service("mqtt/publish", topic=topic, payload=level, retain=True)

    def _set_state(self, entity, brightness):
        self.logme("entity: {}".format(entity), level='debug')
        self.logme("brightness: {}".format(brightness), level='debug')
        if int(brightness) > 0:
            self.logme("turning on", level='debug')
            self.turn_on(entity_id=entity, brightness=brightness)