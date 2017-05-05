from __future__ import division
from matplotlib import rcParams
import numpy as np
import matplotlib.pyplot as plt
import image_helpers as im
import ring_sum as rs
from os.path import join
import fitting
from scipy.optimize import minimize_scalar, fmin, curve_fit, differential_evolution
import time
import cPickle as pickle
from analysis.datahelpers import smooth
import multinest_solver as mns
import multiprocessing as mp
import model

#np.seterr(invalid='ignore')  # I got sick of invalid values that happening during minimization
rcParams['xtick.direction'] = 'in'
rcParams['ytick.direction'] = 'in'

Ar_params = {
    'binsize': 0.1,
    'c_lambda': 487.873302,
    'delta_lambda': 0.0001*4,
    'duc': 0.88,
    'n_dlambda': 512 /4 ,
    'Tlamp': 1000.0 * .025 / 300.0,  # .025 eV per 300 K
    'lampmu': 232.0,
}
He_params = {
    'binsize': 0.1*4.0,
    'c_lambda': 468.6195,
    'delta_lambda': 0.0001*4.0,
    'duc': 0.88,
    'n_dlambda': 512/4,
    'Tlamp': 1000.0 * .025 / 300.0,  # .025 eV per 300 K
    'lampmu': 232.0,
}

def run_calibration(f, f_bg, center_guess, save_dir, gas='Ar', L=None, d=None):
    times = [time.time()]
    x0, y0 = center_guess

    if gas == 'Ar':
        binsize = Ar_params['binsize']
        c_lambda = Ar_params['c_lambda']
        delta_lambda = Ar_params['delta_lambda']
        duc = Ar_params['duc']
        n_dlambda = Ar_params['n_dlambda']
        Tlamp = Ar_params['Tlamp']
        lampmu = Ar_params['lampmu']
    elif gas == 'He':
        binsize = He_params['binsize']
        c_lambda = He_params['c_lambda']
        delta_lambda = He_params['delta_lambda']
        duc = He_params['duc']
        n_dlambda = He_params['n_dlambda']
        Tlamp = He_params['Tlamp']
        lampmu = He_params['lampmu']
    else:
        print "Did not recognize gas.  Exiting..."
        return None
    # f_bg=None
    print f[-3:].lower()
    if f[-3:].lower() == "nef":
        data = im.get_image_data(f, bgname=f_bg, color='b')
    elif f[-3:].lower() == "npy":
        data = np.load(f)
    else:
        print "need a valid file"
        return
    #im.quick_plot(data)
    # plt.show()

    times += [time.time()]
    print "Image done reading, {0} seconds".format(times[-1] - times[-2])
    #x0, y0 = rs.locate_center(data, x0, y0, binsize=binsize, plotit=False)
    times += [time.time()]
    print "Center found, {0} seconds".format(times[-1] - times[-2])

    binarr, sigarr = rs.quick_ringsum(data, x0, y0, binsize=0.4, quadrants=False)
    print len(binarr)
    np.save("rbins2.npy",binarr)
    new_binarr = np.concatenate(([0.0], binarr))
    L, R = fitting.get_peaks(binarr, sigarr, thres1=0.3, npks=8)
    z = fitting.peak_and_fit(binarr, sigarr, thres=0.3, plotit=True)
    print z


    #for i in range(8):
    #    print L[i], R[i]
    inds = [] 
    for i in range(8):
        inds += range(L[i], R[i])
       
    amp0 = np.max(sigarr[L[0]:R[0]])
    amp1 = np.max(sigarr[L[1]:R[1]])

    i = range(L[0], R[0])
    pk0 = np.trapz(binarr[i] * sigarr[i], x=binarr[i]) / np.trapz(sigarr[i], x=binarr[i])

    i = range(L[1],R[1])
    pk1 = np.trapz(binarr[i] * sigarr[i], x=binarr[i]) / np.trapz(sigarr[i], x=binarr[i])
    print pk0, pk1
    r = binarr[inds]

    d =0.884157316074 
    L = 150.535647184 / 0.004
    Q = 20.0

    lambda_0 = 487.873302
    lambda_1 = 487.98634

    Ti0 = 1000.0 * .025 / 300.0   #1000 K in eV
    mu0 = 232.0
    Ti1 = 1000.0 * .025 / 300.0   #1000 K in eV
    mu1 = 40.0 

    sigma0 = 3.276569e-5 * np.sqrt(Ti0/mu0) * lambda_0
    sigma1 = 3.276569e-5 * np.sqrt(Ti1/mu1) * lambda_1
    linear_out = model.forward2(r, L, d, Q, [Ti0, Ti1], [mu0, mu1], [amp0, amp1], [lambda_0, lambda_1])
    #linear_out0 = model.forward(r, L, d, Q, Ti0, mu0, lambda_0)
    #linear_out1 = model.forward(r, L, d, Q, Ti1, mu1, lambda_1)
    #linear_out0 *= 0.5
    #linear_out0 *= 1.5e7
    #linear_out1 *= 1.5e7

    rscale = 4500.0
    fall_off = np.exp(-(r / rscale)**2)
    #linear_out0 *= amp0 / np.exp(-pk0/rscale)
    #linear_out1 *= amp1 / np.exp(-pk1/rscale)

    fig, ax = plt.subplots()
    plt.plot(binarr, sigarr, 'b')
    print len(binarr)
    #ax1 = ax.twinx()
    #ax1.plot(r, fall_off * (linear_out0 + linear_out1), 'r')
    #ax.plot(r, fall_off * (linear_out0 + linear_out1), 'r')
    ax.plot(r, fall_off * linear_out, 'r')
    plt.show()


    finesse_range = [10, 50]
    Ti_Ar_range = [300.0, 11000]
    Ti_Th_range = [300.0, 3000]
    d_range = [.87, .89]
    L_range = [148.0, 151.0]
    a0 = amp0 / np.exp(-(pk0/rscale)**2)
    a1 = amp1 / np.exp(-(pk1/rscale)**2)
    Th_amp_range = [.5*a0, 5.0*a0]
    Ar_amp_range = [.5*a1, 5.0*a1]
    rscale_range = [1000.0, 10000.0]
    
    params = {"finesse_range": finesse_range,
              "Ti_Ar_range": Ti_Ar_range,
              "Ti_Th_range": Ti_Th_range,
              "d_range": d_range,
              "L_range": L_range,
              "Th_amp_range": Th_amp_range,
              "Ar_amp_range": Ar_amp_range,
              "rscale_range": rscale_range,
              "binarr": binarr,
              "ringsum": sigarr,
              "ringsum_sd": 100.0 + 0.01 * sigarr,
              "ind": inds}

    folder = mns.fix_save_directory(save_dir)
    with open(folder + "fp_ringsum_params.p", 'wb') as outfile:
        pickle.dump(params, outfile)


if __name__ == "__main__":
    binsize = 0.1
    folder = "Images"
    fname = join(folder, "thorium_ar_5_min_1.nef")
    bg_fname = join(folder, "thorium_ar_5_min_1_bg.nef")
    save_dir = "full_solver_run5"
    #center_guess = (3068.56, 2033.17)
    center_guess = (3068.57005213, 2032.17646934)
    #folder ="ForwardModelData"
    #fname = join(folder, "th_lamp_FM_14987_8824.npy")
    #bg_fname = None
    #save_dir = "FW_test_14987_8824_0"
    #center_guess = (3018, 2010)
    # Old calibration used to flow
    #fname = join(folder, "Th_lamp_488_calib_5m.nef")
    #bg_fname = join(folder, "Th_lamp_488_calib_5m_background.nef")
    #save_dir = "old_flow_shots"

    #L, d, hwhm, x0, y0 = run_calibration(fname, bg_fname, center_guess, save_dir, gas='Ar')
    run_calibration(fname, bg_fname, center_guess, save_dir, gas='Ar')

    #fname = join(folder, "thorium_5_min_he_3.nef")
    #bg_fname = join(folder, "thorium_5_min_he_bg.nef")
    # center_guess = (3068.39, 2031.85)
    # He guess
    #center_guess = (3040.05627213, 2024.06787634)
   # L, d, hwhm, x0, y0 = run_calibration(fname, bg_fname, center_guess, save_dir, gas='Ar')
