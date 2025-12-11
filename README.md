
# 2025-12-10

Signed up for 60 day trial of DigitalOcean. 

Here is the curl command to create a new droplet on DigitalOcean with monitoring enabled and specific tags:

```
curl -X POST -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer '$TOKEN'' \
    -d '{"name":"ubuntu-s-1vcpu-2gb-sfo3-01",
        "size":"s-1vcpu-2gb",
        "region":"sfo3",
        "image":"ubuntu-24-04-x64",
        "monitoring":true,
        "tags":["networking",
        "minecraft"]}' \
    "https://api.digitalocean.com/v2/droplets"
```

