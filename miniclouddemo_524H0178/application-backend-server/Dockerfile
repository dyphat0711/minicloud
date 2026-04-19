FROM python:3.11-alpine
WORKDIR /app
COPY app.py .
RUN pip install --no-cache-dir flask requests python-jose mysql-connector-python
EXPOSE 8081
CMD ["python","app.py"]
