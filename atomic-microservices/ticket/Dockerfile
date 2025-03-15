FROM python:3-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Patch the graphene package for Python 3.10+ compatibility
RUN sed -i 's/from collections import Iterable, OrderedDict/from collections.abc import Iterable\nfrom collections import OrderedDict/g' \
    $(python -c "import site; print(site.getsitepackages()[0])")/graphene/relay/connection.py
RUN sed -i 's/from collections import Mapping, OrderedDict/from collections.abc import Mapping\nfrom collections import OrderedDict/g' \
    $(python -c "import site; print(site.getsitepackages()[0])")/graphene/types/field.py

# Patch the 'graphql-server' library
RUN sed -i 's/from collections import namedtuple, MutableMapping/from collections import namedtuple\nfrom collections.abc import MutableMapping/g' \
    $(python -c "import site; print(site.getsitepackages()[0])")/graphql_server/__init__.py
    
# # Patch the graphene package for Python 3.10+ compatibility
# RUN sed -i 's/from collections import Iterable/from collections.abc import Iterable/g' /app/venv/lib/python*/site-packages/graphene/relay/connection.py
# RUN sed -i 's/from collections import Mapping/from collections.abc import Mapping/g' /app/venv/lib/python*/site-packages/graphene/types/field.py

# # Patch the 'graphql-server' library
# RUN sed -i 's/from collections import MutableMapping/from collections.abc import MutableMapping/' /app/venv/lib/python*/site-packages/graphql_server/__init__.py

COPY ./ticket.py .
CMD [ "python", "./ticket.py" ]