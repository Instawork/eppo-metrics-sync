from collections import Counter
from itertools import chain

class DbtModelParser():

    def __init__(self, model, dbt_model_prefix):
        self.model = model
        self.eppo_entities = []
        self.eppo_timestamp = []
        self.eppo_facts = []
        self.eppo_properties = []
        self.dbt_model_prefix = dbt_model_prefix

    def _parse_column_entities(self, column, column_entities):

        for column_entity in column_entities:
            column_entity_split = column_entity.split(':')
            # expected format: eppo_entity:<entity name>
            EXPECTED_SPLIT_LENGTH = 2
            assert len(column_entity_split) == EXPECTED_SPLIT_LENGTH, \
                f'Invalid entity tag {column_entity} in model {self.model["name"]}'
            self.eppo_entities.append({
                "entity_name": column_entity_split[1],
                "column": column['name']
            })     


    def _parse_one_column(self, column):

        tags = column.get('tags')

        if tags:

            column_entities = [t for t in tags if 'eppo_entity:' in t]

            if column_entities:
                self._parse_column_entities(column, column_entities)

            if 'eppo_timestamp' in tags:
                self.eppo_timestamp = column["name"]

            fact_entities = [t for t in tags if 'eppo_fact' in t]
            if fact_entities: 
                info = fact_entities[0].split(':')
                name = info[1] if len(info) >= 2 else column["name"]
                desired_change = info[2] if len(info) == 3 else None
                self.eppo_facts.append({
                    "name": name,
                    "column": column["name"],
                    "description": column.get("description", ""),
                    "desired_change": desired_change,
                })

            property_entities = [t for t in tags if 'eppo_property' in t] 
            if property_entities:
                info = property_entities[0].split(':')
                name = info[1] if len(info) == 2 else column["name"]
                self.eppo_properties.append({
                    "name": name,
                    "column": column["name"],
                    "description": column.get("description", "")
                })

    
    def parse_columns(self):

        for column in self.model.get('columns'):
            self._parse_one_column(column)

        # add a default `null` fact if no facts are specified, named after the model
        eppo_row_fact = self.model.get("meta", {}).get("eppo_row_fact")
        if eppo_row_fact is not None:
            name = eppo_row_fact.get("name", self.model["name"])
            description = eppo_row_fact.get("description", "Fact based on the count of rows in the model")
            change = eppo_row_fact.get("desired_change")
            self.eppo_facts.append({
                "name": name,
                "column": None,
                "desired_change": change,
                "description": description,
            })
    
    def validate(self):

        validation_errors = []

        # make sure there is at least one entity and exactly one timestamp
        if len(self.eppo_timestamp) == 0:
            validation_errors.append(
                'Exactly 1 column must be have tag "eppo_timestamp"'
            )
        
        if len(self.eppo_entities) == 0:
            validation_errors.append(
                'At least 1 column must have tag "eppo_entity:<entity_name>"'
            )
        
        # check that no columns are tagged to multiple Eppo fields (skip if there
        # is already a validation error)

        if len(validation_errors) == 0:
            # parse names from column list
            entity_names = [e['column'] for e in self.eppo_entities]
            timestamp_names = [self.eppo_timestamp]
            fact_names = [e['column'] for e in self.eppo_facts]
            property_names = [e['column'] for e in self.eppo_properties]

            all_names = Counter(chain.from_iterable(
                [entity_names, timestamp_names, fact_names, property_names]
            ))

            overlapping_columns = [item for item, count in all_names.items() if count > 1]

            if len(overlapping_columns):
                validation_errors.append(
                    f'The following columns had tags to multiple Eppo fields: {", ".join(overlapping_columns)}'
                )
            
        
        if len(validation_errors):
            raise ValueError(
                f'One or more errors parsing model: {self.model["name"]}: {", ".join(validation_errors)}'
            )

    
    def format(self):

        entity_clause = '\n,'.join([e['column'] for e in self.eppo_entities])
        fact_clause = '\n,'.join([f['column'] for f in self.eppo_facts if f['column']])
        property_clause = '\n,'.join([p['column'] for p in self.eppo_properties])
        entity_clause_sql = f",\n{entity_clause}" if entity_clause else ""
        fact_clause_sql = f",\n{fact_clause}" if fact_clause else ""
        property_clause_sql = f", {property_clause}" if property_clause else ""

        formatted_sql = \
         f"""
        select
            {self.eppo_timestamp}{entity_clause_sql}{fact_clause_sql}{property_clause_sql}
        from 
            {self.dbt_model_prefix}.{self.model['name']}
        """

        fact_source_name = self.model.get("meta", {}).get("eppo_fact_source_name", self.model["name"])
        self.eppo_fact_source = {
            "name":fact_source_name,
            "sql": formatted_sql,
            "timestamp_column": self.eppo_timestamp,
            "entities": self.eppo_entities,
            "facts": self.eppo_facts,
            "properties": self.eppo_properties
        }
    
    def build(self):
        if isinstance(self.model, dict):
            model_tags = self.model.get('tags', [])
            if 'eppo_fact_source' in model_tags:
                self.parse_columns()
                self.validate()
                self.format()
                return self.eppo_fact_source
        else:
            raise ValueError(f"Expected model to be a dictionary, got model = {self.model}")
