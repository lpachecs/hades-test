# HomeController: Initialisation

HomeController is a system level API that can be used to efficiently leverage LDF model functionality across multiple devices. It also provides an API for interacting with HOME System configuration function such as Snapshots, Device Proxies and NMOS.

# Initialisation

```python
from ldf.models.home_controller import HomeController

HOME_IPS = ["10.1.215.71", "10.1.215.72", "10.1.215.73"]


async def create_hoc(home_ips: list[str]):
	"""Produce a HomeController object for use in tests"""
	return await HomeController.create(
		home_addrs=home_ips
	)
	

if __name__ == "__main__":
	home = asyncio.run(create_hoc(HOME_IPS))
	# Do stuff...
	asyncio.run(hoc.close())
```



