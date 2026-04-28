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