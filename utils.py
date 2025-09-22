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

# Expected servers for each company (for sanity checking)
EXPECTED_SERVERS = {
    'BRB Ltd': ['BRBD', 'BRBFAP', 'BRBExchange', 'Remote Desktop'],
    'Lochlie Ltd': ['LochlieApp01', 'LochlieApp02', 'LochlieDC', 'LochlieRD', 'BekatApp02'],
    'eHeating Ltd': ['eHeating02', 'eHeating03', 'eHeating04', 'eHeatingACT'],
    'Caseman Ltd': ['CaseNotes', 'CaseNotesNTS', 'CasemanAPP', 'CasemanA', 'WIN10', 'CasemanDC'],
    'JS Wilson Ltd': ['Remote Desktop', 'Trimble Server'],
    'NHG Ltd': ['NHG'],
    'Bekat IT': ['BekatApp01'],
    'JSW Ltd': ['JSW']
}

def get_company_for_server(server_name):
    """Determine company name based on server name."""
    for key, company in SERVER_COMPANIES.items():
        if key in server_name.upper():
            return company
    return 'Other'  # Default company if no match found

def get_expected_servers(company):
    """Get expected servers for a company."""
    return EXPECTED_SERVERS.get(company, []) 