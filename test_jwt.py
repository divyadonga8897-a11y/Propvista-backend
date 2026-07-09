import jwt

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN2ZGNyZ21wcW9pY3hsZnFteHhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI4NjY1MzgsImV4cCI6MjA5ODQ0MjUzOH0.FuGDSEWbiHXWKDkZ63J0AVTQZUEUdZhV1Otx0IBUBeY"
secret = "8MK+sweg5rhgbbs71M9lzesFR4DnJqeBwEznkUDhOUkZIBboLN/FLWB8h/DYMHS+tE8x9lbuAY1LHSDXQ1Hvrg=="

try:
    payload = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    print(payload)
except Exception as e:
    print(f"Error 1: {type(e).__name__} - {e}")

try:
    payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    print(payload)
except Exception as e:
    print(f"Error 2: {type(e).__name__} - {e}")
