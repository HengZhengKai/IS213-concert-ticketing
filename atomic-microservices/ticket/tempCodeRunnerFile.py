# Define GraphQL Queries
class Query(graphene.ObjectType):
    charge_id = graphene.String(ticketID=graphene.String(required=True))
    is_checked_in = graphene.Boolean(ticketID=graphene.String(required=True))