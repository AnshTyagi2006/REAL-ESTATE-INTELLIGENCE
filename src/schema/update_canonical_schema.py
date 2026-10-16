from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SCHEMA_FILE = (
    ROOT
    / "schema"
    / "canonical_schema.json"
)


def main():

    print("\n" + "=" * 70)
    print("REAL ESTATE INTELLIGENCE PLATFORM")
    print("UPDATING CANONICAL SCHEMA")
    print("=" * 70)

    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(
            f"\nSchema file not found:\n{SCHEMA_FILE}"
        )

    with open(SCHEMA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    schema = data["schema"]
    fields = schema["canonical_fields"]
    aliases = data["aliases"]

    existing_fields = {
        field[0]
        for field in fields
    }

    new_fields = [
        [
            "configuration",
            "string",
            "PROPERTY",
            "optional",
            "Original property configuration such as 3 BHK + Study."
        ],
        [
            "product_type",
            "string",
            "PROPERTY",
            "optional",
            "Source property/product type."
        ],
        [
            "possession",
            "string",
            "PROPERTY",
            "optional",
            "Possession information."
        ],

        [
            "listing_type",
            "string",
            "TRANSACTION",
            "optional",
            "Original listing type."
        ],
        [
            "seller_class",
            "string",
            "TRANSACTION",
            "optional",
            "Source seller classification."
        ],

        [
            "parking",
            "string",
            "FEATURES",
            "optional",
            "Original parking information."
        ],
        [
            "reserved_parking",
            "string",
            "FEATURES",
            "optional",
            "Reserved parking information."
        ],
        [
            "amenities_count",
            "float",
            "FEATURES",
            "optional",
            "Number of amenities reported by the source."
        ],
        [
            "features_count",
            "float",
            "FEATURES",
            "optional",
            "Number of property features reported by the source."
        ],

        [
            "builder",
            "string",
            "PROPERTY",
            "optional",
            "Builder information."
        ],
        [
            "builder_name",
            "string",
            "PROPERTY",
            "optional",
            "Builder/developer name."
        ],

        [
            "seller_agent",
            "string",
            "SOURCE_METADATA",
            "optional",
            "Seller or agent information."
        ]
    ]

    added_fields = []

    for field in new_fields:

        field_name = field[0]

        if field_name not in existing_fields:
            fields.append(field)
            added_fields.append(field_name)

    new_aliases = {

        "configuration": [
            "configuration"
        ],

        "product_type": [
            "product_type"
        ],

        "possession": [
            "possession"
        ],

        "listing_type": [
            "listing_type"
        ],

        "seller_class": [
            "seller_class"
        ],

        "parking": [
            "parking"
        ],

        "reserved_parking": [
            "reserved_parking"
        ],

        "amenities_count": [
            "amenities_count"
        ],

        "features_count": [
            "features_count"
        ],

        "builder": [
            "builder"
        ],

        "builder_name": [
            "builder_name"
        ],

        "seller_agent": [
            "seller_agent"
        ]
    }

    for field_name, field_aliases in new_aliases.items():

        if field_name not in aliases:
            aliases[field_name] = field_aliases
        else:

            for alias in field_aliases:
                if alias not in aliases[field_name]:
                    aliases[field_name].append(alias)

    # Improve existing aliases using the review results.

    aliases["property_name"] = [
        "property_name",
        "property_title",
        "name",
        "building_name",
        "society_name",
        "project_name",
        "proj_name"
    ]

    aliases["locality"] = [
        "locality",
        "locality_clean",
        "locality_wo_city"
    ]

    aliases["price_min_inr"] = [
        "price_min_inr",
        "min_price_inr"
    ]

    aliases["price_max_inr"] = [
        "price_max_inr",
        "max_price_inr"
    ]

    aliases["property_age_years"] = [
        "age_years",
        "property_age"
    ]

    aliases["overlooking"] = [
        "overlooking_raw",
        "overlooking",
        "view_overlooking"
    ]

    aliases["seller_type"] = [
        "seller_type",
        "seller_class"
    ]

    aliases["listing_category"] = [
        "listing_category",
        "listing_type",
        "resale"
    ]

    aliases["parking_count"] = [
        "parking_count"
    ]

    aliases["builder"] = [
        "builder"
    ]

    aliases["builder_name"] = [
        "builder_name"
    ]

    aliases["amenities"] = [
        "amenities_raw",
        "amenities"
    ]

    aliases["features"] = [
        "features_raw",
        "features"
    ]

    with open(
        SCHEMA_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("\nSchema update complete.")

    print(
        f"\nOriginal fields : "
        f"{len(existing_fields)}"
    )

    print(
        f"Final fields    : "
        f"{len(fields)}"
    )

    print(
        f"Fields added    : "
        f"{len(added_fields)}"
    )

    if added_fields:

        print("\nAdded fields:")

        for field in added_fields:
            print(f"  - {field}")

    print("\nImportant:")
    print("property_id will be created by our pipeline.")
    print("It is NOT taken directly from listing_id.")

    print("\nNo property data was modified.")
    print("=" * 70)


if __name__ == "__main__":
    main()