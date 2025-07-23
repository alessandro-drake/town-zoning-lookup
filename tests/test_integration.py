# tests/test_integration.py

import pytest
from ordinance_finder import get_zoning_ordinance

@pytest.mark.integration
def test_live_get_zoning_ordinance_for_arlington():
    """
    Performs a live integration test against the Claude API
    to find the zoning ordinance for Arlington, MA.

    This test makes a real API call and will be skipped by default.
    """
    # Arrange: The city we want to find.
    city_name = "Arlington, MA"

    # Act: Call the real function. This will use the internet and your API key.
    result = get_zoning_ordinance(city_name)

    # Assert: Check for a plausible, successful result.
    # We can't know the exact link, but we can check its basic structure.
    assert result is not None
    assert result.get('city') is not None, "The 'city' field should be populated."
    assert "Arlington" in result['city']

    link = result.get('link')
    assert link is not None, "A link should have been found."
    assert link.lower().startswith('http'), f"Link '{link}' does not appear to be a valid URL."

    print(f"\nLive Test Result for {city_name}:")
    print(f"  Link Found: {result.get('link')}")
    print(f"  File Type: {result.get('file_type')}")
    print(f"  Notes: {result.get('notes')}")

# @pytest.mark.integration
# def test_strict_live_finds_pdf_for_arlington():
#     """
#     Performs a live integration test that fails if a direct PDF link
#     for Arlington's zoning ordinance is not found.
#     """
#     city_name = "Arlington, MA"
#     result = get_zoning_ordinance(city_name) # Makes the live API call

#     # Assert that the outcome meets our strict requirements
#     assert result.get('file_type') == 'PDF', f"Expected file_type to be 'PDF', but got '{result.get('file_type')}'"
    
#     link = result.get('link')
#     assert link and link.lower().startswith('http'), f"A valid URL was not found. Got: '{link}'"
#     assert link.lower().endswith('.pdf'), f"The link found does not point to a PDF. Got: '{link}'"

#     print(f"\nStrict Test PASSED for {city_name}: Found PDF at {link}")