# fibaro-dashboard
Kibana Dashboard for fibaro


To install Elasticsearch and Kibana on a Raspberry Pi, use:
[https://github.com/GuillaumeWaignier/ansible-raspberry-elasticsearch](https://github.com/GuillaumeWaignier/ansible-raspberry-elasticsearch)

To install Neo4J on a Raspberry Pi, use:
[https://github.com/GuillaumeWaignier/ansible-raspberry-neo4j](https://github.com/GuillaumeWaignier/ansible-raspberry-neo4j)


Then to install the cron job that collect the metric do

```bash
ansible-playbook domotique-play.yml --ask-pass
```

To change parameters, such as version, create the file as

```yaml
- name: Install metric collector
  hosts: collector
  roles:
    - role: collector
      tags: collector
  vars:
    - cronMinute: "*/5"
    - fibaro_login: "stats"
    - fibaro_url: "http://192.168.2.13"

  vars_prompt:
    - name: fibaro_password
      prompt: fibaro password
    - name: neo4j_password
      prompt: Neo4j Password
```

The host(s) of the PI are in file _hosts/inventory_.

For the climate, the user needs the access to:
* Temperature sensor
* Humidity sensor
* Light sensor
* Uv sensor

For the power and energy, the user needs the access to:
* power device
* energy device
