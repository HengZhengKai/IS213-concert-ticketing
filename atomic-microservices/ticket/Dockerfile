# Patch the graphene package for Python 3.10+ compatibility
RUN sed -i 's/from collections import Iterable/from collections.abc import Iterable/g' /app/venv/lib/python*/site-packages/graphene/relay/connection.py
RUN sed -i 's/from collections import Mapping/from collections.abc import Mapping/g' /app/venv/lib/python*/site-packages/graphene/types/field.py