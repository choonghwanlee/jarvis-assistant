import coverage
import unittest
import os

# Start measuring code coverage
cov = coverage.Coverage()
cov.start()

# Find and run all tests
loader = unittest.TestLoader()
tests = loader.discover('.', pattern='unit_tests.py')
runner = unittest.TextTestRunner()
runner.run(tests)

# Stop coverage
cov.stop()
cov.save()

# Print coverage report
print("\n--- Coverage Report ---")
cov.report()

# Create HTML report
html_dir = 'coverage_html'
cov.html_report(directory=html_dir)
print(f"\nHTML coverage report created in: {html_dir}")

# Check if we hit target coverage
coverage_percent = cov.report()
if coverage_percent >= 80:
    print(f"✅ Success! Coverage is {coverage_percent:.1f}% (target: 80%)")
else:
    print(f"❌ Coverage is only {coverage_percent:.1f}%, below target of 80%")
