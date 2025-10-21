FROM zauberzeug/nicegui:latest
ENV TZ="Australia/Sydney"
RUN pip install requests pyyaml apscheduler sqlalchemy aiosqlite