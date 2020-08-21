from donphan import Column, SQLType, Table


class Instances(Table):
    guild_id: SQLType.BigInt = Column(primary_key=True, index=True)
    voice_channel_id: SQLType.BigInt = Column(nullablle=False)
    configuration: dict = Column(nullable=False, default={})
