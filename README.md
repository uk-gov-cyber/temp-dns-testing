# DNS TESTING REPO

### Docker commands

To build the image: 

```
docker build -t dnstesting . 
```

and then run with: 

```
docker run -v $(pwd)/app:/app -p 8000:80 --rm -it --name dnstesting-c dnstesting 
```


example curl command: 

```
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "domains": ["example.gov.uk", "service.gov.uk"],
    "record_types": ["A", "MX"]
  }'
```

get something working with aiodns and zdns 
do a write up on findings from dns query mechanisms in domains-api
try locust and tracmalloc