

# Import từ file High_Low.py
from High_Low import get_results

# Hàm để in các kết quả cuối cùng
def print_final_results(final_hh, final_ll, final_hl, final_lh, updated_hh, updated_ll):
    print("\nFinal Higher High (HH):")
    if final_hh:
        print(f"Time: {final_hh[0]}, Value: {final_hh[1]}")
    else:
        print("No Higher High (HH) found.")
    print(f"Updated HH (if any): {updated_hh}")

    print("\nFinal Lower Low (LL):")
    if final_ll:
        print(f"Time: {final_ll[0]}, Value: {final_ll[1]}")
    else:
        print("No Lower Low (LL) found.")
    print(f"Updated LL (if any): {updated_ll}")

    print("\nFinal Higher Low (HL):")
    if final_hl:
        print(f"Time: {final_hl[0]}, Value: {final_hl[1]}")
    else:
        print("No Higher Low (HL) found.")

    print("\nFinal Lower High (LH):")
    if final_lh:
        print(f"Time: {final_lh[0]}, Value: {final_lh[1]}")
    else:
        print("No Lower High (LH) found.")

# Gọi hàm get_results() từ High_Low.py để lấy các kết quả
final_hh, final_ll, final_hl, final_lh, updated_hh, updated_ll = get_results()

# In ra kết quả cuối cùng
print_final_results(final_hh, final_ll, final_hl, final_lh, updated_hh, updated_ll)
