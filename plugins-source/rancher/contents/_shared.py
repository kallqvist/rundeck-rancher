# http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/

def retry(func, timeout):
   def retry_wrapper(*args, **kwargs):
       res = func(*args, **kwargs)
       return ">> {0} ({1}) <<".format(res, timeout)
   return retry_wrapper

@retry(timeout=2)
def stuff():
    return "blabla"

print stuff()
