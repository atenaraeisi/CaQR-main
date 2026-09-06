import argparse
from caqr.modes.qs import run_qs_caqr
from caqr.modes.sr import run_sr_caqr

def main():

    
    # backend = FakeMumbai()
    # Example usage
    parser = argparse.ArgumentParser(description="Qubit reuse pair finder")
    parser.add_argument('--mode', choices=['qs', 'sr'], default='qs',
                        help="CaQR mode to run (default: qs)")
    parser.add_argument('-b','--benchmark', type=str, help="Path to the QASM file")
    parser.add_argument('-v', '--verbose', type=int, default=0,
                        help="Verbosity level (default: 0)")
    parser.add_argument('-w1', '--weight1', type=float, default=1,
                        help="weight for the depth difference (default: 0)")
    parser.add_argument('-w2', '--weight2', type=float, default=1,
                        help="weight for the depth difference (default: 0)")
    parser.add_argument('--device', type=str, default=None,
                        help="Target device for SR-CaQR (not implemented yet)")
    

    args = parser.parse_args()
    if args.mode == 'qs':
        run_qs_caqr(args.benchmark, args.verbose, args.weight1, args.weight2)
    elif args.mode == 'sr':
        run_sr_caqr(args.benchmark, args.device, args.verbose)

if __name__ == '__main__':
    main()
