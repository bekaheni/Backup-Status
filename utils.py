# Server to Company mapping
SERVER_COMPANIES = {
    'LOCHLIE': 'Lochlie Ltd',
    'EHEATING': 'eHeating Ltd',
    'BRB': 'BRB Ltd',
    'CASEMAN': 'Caseman Ltd',
    'JSWILSON': 'JS Wilson Ltd',
    'NHG': 'NHG Ltd',
    'BEKAT': 'Bekat IT',
    'JSW': 'JSW Ltd'
}

def get_company_for_server(server_name):
    """Determine company name based on server name."""
    for key, company in SERVER_COMPANIES.items():
        if key in server_name.upper():
            return company
    return 'Other'  # Default company if no match found 